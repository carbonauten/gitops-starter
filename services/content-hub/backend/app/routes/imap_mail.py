from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..ai_service import ai_configured, draft_email_reply, summarize_article, translate_email_body
from ..audit_service import log_audit
from ..database import get_db
from ..dependencies import require_it_master
from ..imap_config_service import (
    create_imap_account,
    delete_imap_account,
    get_imap_account_row,
    list_imap_accounts,
    update_imap_account,
)
from ..imap_mail_service import get_attachment, get_message, list_folders, list_messages, test_connection
from ..user_integration_store import decrypt_secret

router = APIRouter(prefix="/api/imap-mail", tags=["imap-mail"])


class ImapAccountCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=200)
    host: str = Field(..., min_length=1, max_length=300)
    port: int = Field(default=993, ge=1, le=65535)
    use_ssl: bool = Field(default=True)
    username: str = Field(..., min_length=1, max_length=300)
    password: str = Field(..., min_length=1, max_length=300)
    folder: str = Field(default="INBOX", max_length=200)


class ImapAccountUpdate(BaseModel):
    label: str = Field(..., min_length=1, max_length=200)
    host: str = Field(..., min_length=1, max_length=300)
    port: int = Field(default=993, ge=1, le=65535)
    use_ssl: bool = Field(default=True)
    username: str = Field(..., min_length=1, max_length=300)
    # Blank keeps the stored password - same convention as the create form
    # being the only place a password is required.
    password: str = Field(default="", max_length=300)
    folder: str = Field(default="INBOX", max_length=200)


class ImapSummarizeRequest(BaseModel):
    language: str = Field(default="de", max_length=10)
    folder: str = Field(default="", max_length=200)


class ImapDraftReplyRequest(BaseModel):
    instructions: str = Field(default="", max_length=2000)
    language: str = Field(default="de", max_length=10)
    folder: str = Field(default="", max_length=200)


class ImapTranslateRequest(BaseModel):
    target_language: str = Field(..., max_length=10)
    folder: str = Field(default="", max_length=200)


@router.get("/accounts")
def get_accounts(
    db: Session = Depends(get_db),
    _user: dict = Depends(require_it_master),
) -> dict:
    return {"accounts": list_imap_accounts(db)}


@router.post("/accounts", status_code=201)
def post_account(
    payload: ImapAccountCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_it_master),
) -> dict:
    # Fail fast with a clear, translated error (wrong host/port/password) instead
    # of only finding out once someone later opens the mailbox.
    test_connection(
        host=payload.host,
        port=payload.port,
        use_ssl=payload.use_ssl,
        username=payload.username,
        password=payload.password,
        folder=payload.folder,
    )
    account = create_imap_account(
        db,
        label=payload.label,
        host=payload.host,
        port=payload.port,
        use_ssl=payload.use_ssl,
        username=payload.username,
        password=payload.password,
        folder=payload.folder,
        actor=user,
    )
    log_audit(db, entity_type="imap_mail_account", entity_id=account["id"], action="created", actor=user)
    return {"account": account}


@router.put("/accounts/{account_id}")
def put_account(
    account_id: str,
    payload: ImapAccountUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_it_master),
) -> dict:
    existing = get_imap_account_row(db, account_id)
    # Same fail-fast test as on create, using the new password if one was
    # given, otherwise the still-encrypted stored one (blank means "keep").
    effective_password = payload.password or decrypt_secret(existing.password_enc or "")
    test_connection(
        host=payload.host,
        port=payload.port,
        use_ssl=payload.use_ssl,
        username=payload.username,
        password=effective_password,
        folder=payload.folder,
    )
    account = update_imap_account(
        db,
        account_id,
        label=payload.label,
        host=payload.host,
        port=payload.port,
        use_ssl=payload.use_ssl,
        username=payload.username,
        password=payload.password,
        folder=payload.folder,
    )
    log_audit(db, entity_type="imap_mail_account", entity_id=account_id, action="updated", actor=user)
    return {"account": account}


@router.delete("/accounts/{account_id}", status_code=204)
def delete_account_route(
    account_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_it_master),
):
    delete_imap_account(db, account_id)
    log_audit(db, entity_type="imap_mail_account", entity_id=account_id, action="deleted", actor=user)
    return Response(status_code=204)


@router.get("/accounts/{account_id}/folders")
def get_folders_route(
    account_id: str,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_it_master),
) -> dict:
    return {"folders": list_folders(db, account_id=account_id)}


@router.get("/accounts/{account_id}/messages")
def get_messages_route(
    account_id: str,
    top: int = 30,
    q: str = "",
    folder: str = "",
    db: Session = Depends(get_db),
    _user: dict = Depends(require_it_master),
) -> dict:
    return {"messages": list_messages(db, account_id=account_id, limit=top, search=q, folder=folder or None)}


@router.get("/accounts/{account_id}/messages/{message_id}")
def get_message_route(
    account_id: str,
    message_id: str,
    folder: str = "",
    db: Session = Depends(get_db),
    _user: dict = Depends(require_it_master),
) -> dict:
    return {"message": get_message(db, account_id=account_id, message_id=message_id, folder=folder or None)}


@router.get("/accounts/{account_id}/messages/{message_id}/attachments/{attachment_index}")
def get_attachment_route(
    account_id: str,
    message_id: str,
    attachment_index: int,
    folder: str = "",
    db: Session = Depends(get_db),
    _user: dict = Depends(require_it_master),
) -> Response:
    content, filename, content_type = get_attachment(
        db,
        account_id=account_id,
        message_id=message_id,
        attachment_index=attachment_index,
        folder=folder or None,
    )
    safe_filename = filename.replace('"', "").replace("\r", "").replace("\n", "")
    return Response(
        content=content,
        media_type=content_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
    )


@router.post("/accounts/{account_id}/messages/{message_id}/summarize")
def summarize_message_route(
    account_id: str,
    message_id: str,
    payload: ImapSummarizeRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_it_master),
) -> dict:
    if not ai_configured():
        raise HTTPException(status_code=503, detail="ai_not_configured")
    message = get_message(db, account_id=account_id, message_id=message_id, folder=payload.folder or None)
    summary = summarize_article(
        title=str(message.get("subject") or ""),
        content=str(message.get("body") or ""),
        language=payload.language,
    )
    if not summary:
        raise HTTPException(status_code=502, detail="ai_summary_failed")
    return {"summary": summary}


@router.post("/accounts/{account_id}/messages/{message_id}/draft-reply")
def draft_reply_route(
    account_id: str,
    message_id: str,
    payload: ImapDraftReplyRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_it_master),
) -> dict:
    if not ai_configured():
        raise HTTPException(status_code=503, detail="ai_not_configured")
    message = get_message(db, account_id=account_id, message_id=message_id, folder=payload.folder or None)
    reply = draft_email_reply(
        subject=str(message.get("subject") or ""),
        body=str(message.get("body") or ""),
        sender_name=str((message.get("from") or {}).get("name") or ""),
        instructions=payload.instructions,
        language=payload.language,
    )
    if not reply:
        raise HTTPException(status_code=502, detail="ai_draft_failed")
    return {"reply": reply}


@router.post("/accounts/{account_id}/messages/{message_id}/translate")
def translate_message_route(
    account_id: str,
    message_id: str,
    payload: ImapTranslateRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_it_master),
) -> dict:
    if not ai_configured():
        raise HTTPException(status_code=503, detail="ai_not_configured")
    message = get_message(db, account_id=account_id, message_id=message_id, folder=payload.folder or None)
    translated = translate_email_body(
        body=str(message.get("body") or ""),
        body_type=str(message.get("body_type") or "text"),
        target_language=payload.target_language,
    )
    if not translated:
        raise HTTPException(status_code=502, detail="ai_translation_failed")
    return {"translation": {"body": translated, "body_type": message.get("body_type") or "text"}}
