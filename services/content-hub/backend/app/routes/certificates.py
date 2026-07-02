from __future__ import annotations

import csv
import io
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..dependencies import get_current_user, require_editor
from ..certificates import compute_certificate_status, days_until_expiry, expiry_window_end
from ..database import Certificate, FileAsset, get_db
from ..schemas import CertificateCreate, CertificateResponse, CertificateUpdate

router = APIRouter(prefix="/api/certificates", tags=["certificates"])

VALID_CATEGORIES = {"compliance", "product", "training", "ssl"}
VALID_STATUSES = {"valid", "expiring", "expired", "renewal"}


def _file_name(db: Session, file_asset_id: Optional[str]) -> Optional[str]:
    if not file_asset_id:
        return None
    file_asset = db.get(FileAsset, file_asset_id)
    return file_asset.original_name if file_asset else None


def _validate_file_asset(db: Session, file_asset_id: Optional[str]) -> None:
    if not file_asset_id:
        return
    if not db.get(FileAsset, file_asset_id):
        raise HTTPException(status_code=404, detail="not_found")


def _to_response(certificate: Certificate, db: Session, today: Optional[date] = None) -> CertificateResponse:
    today = today or date.today()
    return CertificateResponse(
        id=certificate.id,
        name=certificate.name,
        category=certificate.category,
        issuer=certificate.issuer,
        valid_from=certificate.valid_from,
        valid_to=certificate.valid_to,
        renewal_in_progress=certificate.renewal_in_progress,
        status=compute_certificate_status(certificate.valid_to, certificate.renewal_in_progress, today),
        days_until_expiry=days_until_expiry(certificate.valid_to, today),
        responsible_name=certificate.responsible_name,
        responsible_email=certificate.responsible_email,
        file_asset_id=certificate.file_asset_id,
        file_name=_file_name(db, certificate.file_asset_id),
        notes=certificate.notes,
        created_by_id=certificate.created_by_id,
        created_by_name=certificate.created_by_name,
        created_at=certificate.created_at,
        updated_at=certificate.updated_at,
    )


def _validate_dates(valid_from: date, valid_to: date) -> None:
    if valid_to < valid_from:
        raise HTTPException(status_code=422, detail="validation")


@router.get("")
def list_certificates(
    q: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict:
    today = date.today()
    stmt = select(Certificate).order_by(Certificate.valid_to.asc())
    if category in VALID_CATEGORIES:
        stmt = stmt.where(Certificate.category == category)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Certificate.name.ilike(pattern),
                Certificate.issuer.ilike(pattern),
                Certificate.responsible_name.ilike(pattern),
            )
        )
    certificates = db.scalars(stmt).all()
    responses = [_to_response(certificate, db, today) for certificate in certificates]
    if status in VALID_STATUSES:
        responses = [item for item in responses if item.status == status]
    return {"certificates": responses}


@router.get("/export")
def export_certificates(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> StreamingResponse:
    today = date.today()
    certificates = db.scalars(select(Certificate).order_by(Certificate.valid_to.asc())).all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "name",
            "category",
            "issuer",
            "valid_from",
            "valid_to",
            "status",
            "days_until_expiry",
            "responsible_name",
            "responsible_email",
            "renewal_in_progress",
            "notes",
        ]
    )
    for certificate in certificates:
        response = _to_response(certificate, db, today)
        writer.writerow(
            [
                response.name,
                response.category,
                response.issuer,
                response.valid_from.isoformat(),
                response.valid_to.isoformat(),
                response.status,
                response.days_until_expiry,
                response.responsible_name,
                response.responsible_email,
                response.renewal_in_progress,
                response.notes,
            ]
        )
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="certificates.csv"'},
    )


@router.post("", status_code=201)
def create_certificate(
    payload: CertificateCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_editor),
) -> dict:
    _validate_dates(payload.valid_from, payload.valid_to)
    _validate_file_asset(db, payload.file_asset_id)
    certificate = Certificate(
        name=payload.name,
        category=payload.category,
        issuer=payload.issuer,
        valid_from=payload.valid_from,
        valid_to=payload.valid_to,
        renewal_in_progress=payload.renewal_in_progress,
        responsible_name=payload.responsible_name,
        responsible_email=payload.responsible_email,
        file_asset_id=payload.file_asset_id,
        notes=payload.notes,
        created_by_id=user["id"],
        created_by_name=user["name"],
    )
    db.add(certificate)
    db.commit()
    db.refresh(certificate)
    return {"certificate": _to_response(certificate, db)}


@router.get("/{certificate_id}")
def get_certificate(
    certificate_id: str,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict:
    certificate = db.get(Certificate, certificate_id)
    if not certificate:
        raise HTTPException(status_code=404, detail="not_found")
    return {"certificate": _to_response(certificate, db)}


@router.patch("/{certificate_id}")
def update_certificate(
    certificate_id: str,
    payload: CertificateUpdate,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_editor),
) -> dict:
    certificate = db.get(Certificate, certificate_id)
    if not certificate:
        raise HTTPException(status_code=404, detail="not_found")

    if payload.name is not None:
        certificate.name = payload.name
    if payload.category is not None:
        certificate.category = payload.category
    if payload.issuer is not None:
        certificate.issuer = payload.issuer
    if payload.valid_from is not None:
        certificate.valid_from = payload.valid_from
    if payload.valid_to is not None:
        certificate.valid_to = payload.valid_to
    if payload.renewal_in_progress is not None:
        certificate.renewal_in_progress = payload.renewal_in_progress
    if payload.responsible_name is not None:
        certificate.responsible_name = payload.responsible_name
    if payload.responsible_email is not None:
        certificate.responsible_email = payload.responsible_email
    if payload.file_asset_id is not None:
        _validate_file_asset(db, payload.file_asset_id)
        certificate.file_asset_id = payload.file_asset_id
    if payload.notes is not None:
        certificate.notes = payload.notes

    _validate_dates(certificate.valid_from, certificate.valid_to)
    db.commit()
    db.refresh(certificate)
    return {"certificate": _to_response(certificate, db)}


@router.delete("/{certificate_id}", status_code=204)
def delete_certificate(
    certificate_id: str,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_editor),
):
    certificate = db.get(Certificate, certificate_id)
    if not certificate:
        raise HTTPException(status_code=404, detail="not_found")
    db.delete(certificate)
    db.commit()
    return Response(status_code=204)
