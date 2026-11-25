from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..mailbox_org_service import (
    connect_mailbox_org,
    disconnect_mailbox_org,
    mailbox_org_attachment,
    mailbox_org_folders,
    mailbox_org_message,
    mailbox_org_messages,
    mailbox_org_status,
)
from ..schemas import MailboxOrgConnectRequest

router = APIRouter(prefix="/api/integrations/mailbox-org", tags=["mailbox-org"])


@router.get("/status")
def mailbox_org_status_route(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict:
    return mailbox_org_status(db, user_id=user.get("db_id", ""))


@router.post("/connect")
def mailbox_org_connect_route(
    payload: MailboxOrgConnectRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict:
    return connect_mailbox_org(db, user_id=user.get("db_id", ""), email=payload.email, password=payload.password)


@router.delete("")
def mailbox_org_disconnect_route(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict:
    disconnect_mailbox_org(db, user_id=user.get("db_id", ""))
    return {"ok": True}


@router.get("/folders")
def mailbox_org_folders_route(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict:
    return {"folders": mailbox_org_folders(db, user_id=user.get("db_id", ""))}


@router.get("/messages")
def mailbox_org_messages_route(
    top: int = 30,
    q: str = "",
    folder: str = "",
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict:
    messages = mailbox_org_messages(
        db, user_id=user.get("db_id", ""), limit=top, search=q, folder=folder or None
    )
    return {"messages": messages}


@router.get("/messages/{message_id}")
def mailbox_org_message_route(
    message_id: str,
    folder: str = "",
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict:
    message = mailbox_org_message(
        db, user_id=user.get("db_id", ""), message_id=message_id, folder=folder or None
    )
    return {"message": message}


@router.get("/messages/{message_id}/attachments/{attachment_index}")
def mailbox_org_attachment_route(
    message_id: str,
    attachment_index: int,
    folder: str = "",
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> Response:
    content, filename, content_type = mailbox_org_attachment(
        db,
        user_id=user.get("db_id", ""),
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
