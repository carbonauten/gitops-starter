from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..wopi_service import (
    check_file_info,
    get_file_contents,
    get_lock,
    lock,
    parse_wopi_token,
    put_file,
    refresh_lock,
    unlock,
)

# No cookie/session auth here on purpose: Collabora's SERVER calls these
# endpoints directly (never through the editor's browser tab), authenticated
# solely by the access_token query param WOPI puts on every request.
router = APIRouter(prefix="/wopi/files", tags=["wopi"])


def _require_token(request: Request, file_id: str) -> dict:
    token = request.query_params.get("access_token", "")
    if not token:
        raise HTTPException(status_code=401, detail="wopi_token_invalid")
    payload = parse_wopi_token(token)
    if payload.get("file_id") != file_id:
        raise HTTPException(status_code=401, detail="wopi_token_invalid")
    return payload


@router.get("/{file_id}")
def wopi_check_file_info(
    file_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    payload = _require_token(request, file_id)
    return check_file_info(db, file_id=file_id, token_payload=payload)


@router.get("/{file_id}/contents")
def wopi_get_file(
    file_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    _require_token(request, file_id)
    content = get_file_contents(db, file_id=file_id)
    return Response(content=content, media_type="application/octet-stream")


@router.post("/{file_id}/contents")
async def wopi_put_file(
    file_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    _require_token(request, file_id)
    content = await request.body()
    provided_lock = request.headers.get("X-WOPI-Lock", "")
    status_code = put_file(db, file_id=file_id, content=content, provided_lock=provided_lock)
    return JSONResponse({}, status_code=status_code)


@router.post("/{file_id}")
async def wopi_file_operations(
    file_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    """Multiplexed Lock/GetLock/RefreshLock/Unlock/UnlockAndRelock, as the
    WOPI spec requires: all POST to the bare file URL, disambiguated by the
    X-WOPI-Override header."""
    _require_token(request, file_id)
    override = request.headers.get("X-WOPI-Override", "")
    requested_lock = request.headers.get("X-WOPI-Lock", "")

    if override == "LOCK":
        status_code, current_lock = lock(file_id, new_lock=requested_lock)
    elif override == "GET_LOCK":
        status_code, current_lock = 200, get_lock(file_id)
    elif override == "REFRESH_LOCK":
        status_code, current_lock = refresh_lock(file_id, expected_lock=requested_lock)
    elif override == "UNLOCK":
        status_code, current_lock = unlock(file_id, expected_lock=requested_lock)
    elif override == "UNLOCK_AND_RELOCK":
        old_lock = request.headers.get("X-WOPI-OldLock", "")
        unlock_status, _ = unlock(file_id, expected_lock=old_lock)
        if unlock_status != 200:
            status_code, current_lock = unlock_status, get_lock(file_id)
        else:
            status_code, current_lock = lock(file_id, new_lock=requested_lock)
    else:
        raise HTTPException(status_code=501, detail="wopi_operation_unsupported")

    response = JSONResponse({}, status_code=status_code)
    response.headers["X-WOPI-Lock"] = current_lock
    return response
