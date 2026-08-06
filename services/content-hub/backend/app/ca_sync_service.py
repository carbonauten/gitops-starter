"""CA auto-import: upsert SSL certs from files, Let's Encrypt dirs, Azure Key Vault."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .database import Certificate, FileAsset
from .ssl_cert_parser import ParsedSslCertificate, parse_ssl_certificate, try_parse_ssl_certificate
from .storage import read_upload, save_upload

logger = logging.getLogger(__name__)

SOURCE_SSL_FILE = "ssl_file"
SOURCE_LETSENCRYPT = "letsencrypt"
SOURCE_KEY_VAULT = "key_vault"


def ca_sync_status(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    live_dir = (settings.letsencrypt_live_dir or "").strip()
    vault_url = (settings.azure_key_vault_url or "").strip().rstrip("/")
    return {
        "ssl_file_import": True,
        "letsencrypt_configured": bool(live_dir and Path(live_dir).is_dir()),
        "letsencrypt_live_dir": live_dir,
        "key_vault_configured": bool(vault_url and settings.entra_configured),
        "key_vault_url": vault_url,
        "key_vault_mock": bool(settings.key_vault_mock_mode),
    }


def find_by_fingerprint(db: Session, fingerprint: str) -> Certificate | None:
    if not fingerprint:
        return None
    return db.scalar(select(Certificate).where(Certificate.fingerprint == fingerprint).limit(1))


def find_by_external(db: Session, source: str, external_id: str) -> Certificate | None:
    if not source or not external_id:
        return None
    return db.scalar(
        select(Certificate)
        .where(Certificate.external_source == source, Certificate.external_id == external_id)
        .limit(1)
    )


def upsert_ssl_certificate(
    db: Session,
    *,
    parsed: ParsedSslCertificate,
    user: dict[str, Any],
    source: str,
    external_id: str | None = None,
    file_asset_id: str | None = None,
    notes: str = "",
    responsible_name: str = "",
    responsible_email: str = "",
    escalate_email: str = "",
) -> tuple[Certificate, bool]:
    """Create or update certificate by fingerprint / external id. Returns (cert, created)."""
    external_id = (external_id or parsed.fingerprint_sha256)[:200]
    existing = find_by_fingerprint(db, parsed.fingerprint_sha256) or find_by_external(db, source, external_id)
    note_bits = [notes.strip()] if notes.strip() else []
    meta = f"Auto-Import ({source}) · fingerprint {parsed.fingerprint_sha256[:16]}…"
    if parsed.sans:
        meta = f"{meta} · SAN: {', '.join(parsed.sans[:5])}"
    note_bits.append(meta)
    combined_notes = "\n".join(bit for bit in note_bits if bit)[:4000]

    if existing:
        existing.name = parsed.name
        existing.category = "ssl"
        existing.issuer = parsed.issuer
        existing.valid_from = parsed.valid_from
        existing.valid_to = parsed.valid_to
        existing.fingerprint = parsed.fingerprint_sha256
        existing.external_source = source
        existing.external_id = external_id
        if file_asset_id:
            existing.file_asset_id = file_asset_id
        if combined_notes:
            existing.notes = combined_notes
        if responsible_name:
            existing.responsible_name = responsible_name
        if responsible_email:
            existing.responsible_email = responsible_email
        if escalate_email:
            existing.escalate_email = escalate_email
        db.commit()
        db.refresh(existing)
        return existing, False

    certificate = Certificate(
        name=parsed.name,
        category="ssl",
        issuer=parsed.issuer,
        valid_from=parsed.valid_from,
        valid_to=parsed.valid_to,
        fingerprint=parsed.fingerprint_sha256,
        external_source=source,
        external_id=external_id,
        file_asset_id=file_asset_id,
        notes=combined_notes,
        responsible_name=responsible_name,
        responsible_email=responsible_email,
        escalate_email=escalate_email,
        created_by_id=user.get("id") or "",
        created_by_name=user.get("name") or "CA Sync",
    )
    db.add(certificate)
    db.commit()
    db.refresh(certificate)
    return certificate, True


def store_pem_as_file_asset(db: Session, *, pem: bytes, filename: str, user: dict[str, Any]) -> FileAsset:
    stored_name, storage_path, _path = save_upload(pem, filename)
    asset = FileAsset(
        original_name=filename[:300],
        stored_name=stored_name,
        content_type="application/x-pem-file",
        size_bytes=len(pem),
        storage_path=storage_path,
        folder="certificates",
        uploaded_by_id=user.get("id") or "",
        uploaded_by_name=user.get("name") or "CA Sync",
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def parse_file_asset(db: Session, file_asset_id: str) -> ParsedSslCertificate:
    asset = db.get(FileAsset, file_asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="not_found")
    content = read_upload(asset.storage_path)
    return parse_ssl_certificate(content, preferred_name=Path(asset.original_name).stem.replace("_", " ").replace("-", " "))


def sync_letsencrypt_dir(db: Session, *, user: dict[str, Any], settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    root = Path((settings.letsencrypt_live_dir or "").strip())
    if not root.is_dir():
        raise HTTPException(status_code=400, detail="letsencrypt_not_configured")

    created = 0
    updated = 0
    skipped = 0
    errors: list[str] = []
    for domain_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        cert_path = domain_dir / "cert.pem"
        if not cert_path.exists():
            cert_path = domain_dir / "fullchain.pem"
        if not cert_path.exists():
            skipped += 1
            continue
        try:
            raw = cert_path.read_bytes()
            parsed = parse_ssl_certificate(raw, preferred_name=domain_dir.name)
            asset = store_pem_as_file_asset(
                db,
                pem=raw,
                filename=f"{domain_dir.name}.pem",
                user=user,
            )
            _cert, was_created = upsert_ssl_certificate(
                db,
                parsed=parsed,
                user=user,
                source=SOURCE_LETSENCRYPT,
                external_id=f"le:{domain_dir.name}",
                file_asset_id=asset.id,
                notes=f"Let's Encrypt live: {cert_path}",
            )
            if was_created:
                created += 1
            else:
                updated += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("Let's Encrypt sync failed for %s: %s", domain_dir.name, exc)
            errors.append(f"{domain_dir.name}: {exc}")

    return {
        "source": SOURCE_LETSENCRYPT,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors[:20],
    }


def _mock_key_vault_certs() -> list[tuple[str, bytes]]:
    """Deterministic mock certs for local/CI without Azure."""
    from datetime import datetime, timedelta, timezone

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    items: list[tuple[str, bytes]] = []
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(timezone.utc)
    for name in ("app-carbonauten-com", "fuckco2-shop"):
        subject = issuer = x509.Name(
            [
                x509.NameAttribute(NameOID.COMMON_NAME, name.replace("-", ".")),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Azure Key Vault Mock"),
            ]
        )
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=10))
            .not_valid_after(now + timedelta(days=120))
            .sign(key, hashes.SHA256())
        )
        items.append((name, cert.public_bytes(serialization.Encoding.PEM)))
    return items


async def _fetch_key_vault_certificates(settings: Settings) -> list[tuple[str, bytes]]:
    if settings.key_vault_mock_mode:
        return _mock_key_vault_certs()

    vault = (settings.azure_key_vault_url or "").strip().rstrip("/")
    if not vault or not settings.entra_configured:
        raise HTTPException(status_code=400, detail="key_vault_not_configured")

    token_url = f"https://login.microsoftonline.com/{settings.azure_tenant_id}/oauth2/v2.0/token"
    async with httpx.AsyncClient(timeout=30.0) as client:
        token_resp = await client.post(
            token_url,
            data={
                "client_id": settings.azure_client_id,
                "client_secret": settings.azure_client_secret,
                "scope": "https://vault.azure.net/.default",
                "grant_type": "client_credentials",
            },
        )
        if token_resp.status_code >= 400:
            logger.warning("Key Vault token failed: %s", token_resp.text[:300])
            raise HTTPException(status_code=502, detail="key_vault_token_failed")
        access_token = token_resp.json().get("access_token") or ""
        headers = {"Authorization": f"Bearer {access_token}"}

        list_resp = await client.get(f"{vault}/certificates?api-version=7.4", headers=headers)
        if list_resp.status_code >= 400:
            raise HTTPException(status_code=502, detail="key_vault_list_failed")
        values = list_resp.json().get("value") or []
        results: list[tuple[str, bytes]] = []
        for item in values:
            cert_id = (item.get("id") or "").rstrip("/")
            if not cert_id:
                continue
            name = cert_id.rsplit("/", 1)[-1]
            cer_resp = await client.get(f"{cert_id}?api-version=7.4", headers=headers)
            if cer_resp.status_code >= 400:
                continue
            cer_b64 = (cer_resp.json().get("cer") or "").strip()
            if not cer_b64:
                continue
            import base64

            try:
                der = base64.b64decode(cer_b64)
            except Exception:  # noqa: BLE001
                continue
            # Wrap DER as PEM for storage consistency
            from cryptography.hazmat.primitives.serialization import Encoding
            from cryptography import x509 as cx509

            try:
                x509_cert = cx509.load_der_x509_certificate(der)
                pem = x509_cert.public_bytes(Encoding.PEM)
            except Exception:  # noqa: BLE001
                continue
            results.append((name, pem))
        return results


async def sync_key_vault(db: Session, *, user: dict[str, Any], settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    status = ca_sync_status(settings)
    if not status["key_vault_configured"] and not status["key_vault_mock"]:
        raise HTTPException(status_code=400, detail="key_vault_not_configured")

    created = 0
    updated = 0
    errors: list[str] = []
    items = await _fetch_key_vault_certificates(settings)
    for name, pem in items:
        try:
            parsed = parse_ssl_certificate(pem, preferred_name=name.replace("-", "."))
            asset = store_pem_as_file_asset(db, pem=pem, filename=f"{name}.pem", user=user)
            _cert, was_created = upsert_ssl_certificate(
                db,
                parsed=parsed,
                user=user,
                source=SOURCE_KEY_VAULT,
                external_id=f"kv:{name}",
                file_asset_id=asset.id,
                notes=f"Azure Key Vault: {name}",
            )
            if was_created:
                created += 1
            else:
                updated += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("Key Vault sync failed for %s: %s", name, exc)
            errors.append(f"{name}: {exc}")

    return {
        "source": SOURCE_KEY_VAULT,
        "created": created,
        "updated": updated,
        "skipped": 0,
        "errors": errors[:20],
        "mock": bool(settings.key_vault_mock_mode),
    }


def maybe_enrich_from_file_asset(db: Session, file_asset_id: str | None) -> ParsedSslCertificate | None:
    if not file_asset_id:
        return None
    asset = db.get(FileAsset, file_asset_id)
    if not asset:
        return None
    try:
        content = read_upload(asset.storage_path)
    except Exception:  # noqa: BLE001
        return None
    if not try_parse_ssl_certificate(content, preferred_name=""):
        # try_parse already returns None on failure; also check extension
        from .ssl_cert_parser import looks_like_ssl_bytes

        if not looks_like_ssl_bytes(content, asset.original_name):
            return None
    return try_parse_ssl_certificate(
        content,
        preferred_name=Path(asset.original_name).stem.replace("_", " ").replace("-", " "),
    )
