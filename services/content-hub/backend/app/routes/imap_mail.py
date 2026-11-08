from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..ai_service import ai_configured, summarize_article
from ..audit_service import log_audit
from ..database import get_db
from ..dependencies import require_it_master
from ..imap_config_service import create_imap_account, delete_imap_account, list_imap_accounts
from ..imap_mail_service import get_message, list_messages, test_connection

router = APIRouter(prefix="/api/imap-mail", tags=["imap-mail"])


class ImapAccountCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=200)
    host: str = Field(..., min_length=1, max_length=300)
    port: int = Field(default=993, ge=1, le=65535)
    use_ssl: bool = Field(default=True)
    username: str = Field(..., min_length=1, max_length=300)
    password: str = Field(..., min_length=1, max_length=300)
    folder: str = Field(default="INBOX", max_length=200)


class ImapSummarizeRequest(BaseModel):
    language: str = Field(default="de", max_length=10)


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


@router.delete("/accounts/{account_id}", status_code=204)
def delete_account_route(
    account_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_it_master),
):
    delete_imap_account(db, account_id)
    log_audit(db, entity_type="imap_mail_account", entity_id=account_id, action="deleted", actor=user)
    return Response(status_code=204)


@router.get("/accounts/{account_id}/messages")
def get_messages_route(
    account_id: str,
    top: int = 30,
    q: str = "",
    db: Session = Depends(get_db),
    _user: dict = Depends(require_it_master),
) -> dict:
    return {"messages": list_messages(db, account_id=account_id, limit=top, search=q)}


@router.get("/accounts/{account_id}/messages/{message_id}")
def get_message_route(
    account_id: str,
    message_id: str,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_it_master),
) -> dict:
    return {"message": get_message(db, account_id=account_id, message_id=message_id)}


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
    message = get_message(db, account_id=account_id, message_id=message_id)
    summary = summarize_article(
        title=str(message.get("subject") or ""),
        content=str(message.get("body") or ""),
        language=payload.language,
    )
    if not summary:
        raise HTTPException(status_code=502, detail="ai_summary_failed")
    return {"summary": summary}
