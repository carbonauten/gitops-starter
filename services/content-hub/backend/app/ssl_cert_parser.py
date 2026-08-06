"""Parse SSL/TLS certificates (PEM / DER / CRT) for auto-import."""

from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Any

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509.oid import ExtensionOID, NameOID, ObjectIdentifier
from fastapi import HTTPException


PEM_CERT_RE = re.compile(
    rb"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
    re.DOTALL,
)


@dataclass
class ParsedSslCertificate:
    name: str
    issuer: str
    valid_from: date
    valid_to: date
    fingerprint_sha256: str
    serial_number: str
    subject: str
    sans: list[str]
    is_lets_encrypt: bool

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["valid_from"] = self.valid_from.isoformat()
        payload["valid_to"] = self.valid_to.isoformat()
        payload["category"] = "ssl"
        return payload


def _as_utc_date(value: datetime) -> date:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).date()
    return value.astimezone(timezone.utc).date()


def _cert_not_before(cert: x509.Certificate) -> date:
    value = getattr(cert, "not_valid_before_utc", None) or cert.not_valid_before
    return _as_utc_date(value)


def _cert_not_after(cert: x509.Certificate) -> date:
    value = getattr(cert, "not_valid_after_utc", None) or cert.not_valid_after
    return _as_utc_date(value)


def _name_attr(name: x509.Name, oid: ObjectIdentifier) -> str:
    attrs = name.get_attributes_for_oid(oid)
    if not attrs:
        return ""
    return str(attrs[0].value).strip()


def _format_name(name: x509.Name) -> str:
    cn = _name_attr(name, NameOID.COMMON_NAME)
    if cn:
        return cn
    org = _name_attr(name, NameOID.ORGANIZATION_NAME)
    if org:
        return org
    return name.rfc4514_string()[:500]


def _extract_sans(cert: x509.Certificate) -> list[str]:
    try:
        ext = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
    except x509.ExtensionNotFound:
        return []
    values: list[str] = []
    for general in ext.value:
        try:
            values.append(str(general.value))
        except Exception:  # noqa: BLE001
            continue
    return values[:50]


def load_x509_certificates(raw: bytes) -> list[x509.Certificate]:
    if not raw:
        raise HTTPException(status_code=422, detail="invalid_ssl_certificate")
    content = raw.strip()
    certs: list[x509.Certificate] = []

    pem_blocks = PEM_CERT_RE.findall(content)
    if pem_blocks:
        for block in pem_blocks:
            try:
                certs.append(x509.load_pem_x509_certificate(block, default_backend()))
            except Exception:  # noqa: BLE001
                continue
        if certs:
            return certs

    if b"BEGIN CERTIFICATE" in content:
        try:
            return [x509.load_pem_x509_certificate(content, default_backend())]
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=422, detail="invalid_ssl_certificate") from exc

    try:
        return [x509.load_der_x509_certificate(content, default_backend())]
    except Exception:
        pass

    try:
        decoded = base64.b64decode(content, validate=False)
        return [x509.load_der_x509_certificate(decoded, default_backend())]
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail="invalid_ssl_certificate") from exc


def looks_like_ssl_bytes(raw: bytes, filename: str = "") -> bool:
    lower = (filename or "").lower()
    if lower.endswith((".pem", ".crt", ".cer", ".der", ".cert")):
        return True
    sample = (raw or b"")[:2048]
    return b"BEGIN CERTIFICATE" in sample


def parse_ssl_certificate(raw: bytes, *, preferred_name: str = "") -> ParsedSslCertificate:
    """Parse leaf certificate (first in chain) and extract metadata."""
    certs = load_x509_certificates(raw)
    cert = certs[0]
    subject = _format_name(cert.subject)
    issuer = _format_name(cert.issuer)
    sans = _extract_sans(cert)
    name = subject or (sans[0] if sans else "") or (preferred_name or "").strip() or "SSL Certificate"
    fingerprint = hashlib.sha256(cert.public_bytes(encoding=Encoding.DER)).hexdigest()
    issuer_blob = f"{issuer} {cert.issuer.rfc4514_string()}".lower()
    is_le = "let's encrypt" in issuer_blob or "letsencrypt" in issuer_blob.replace(" ", "")
    return ParsedSslCertificate(
        name=name[:500],
        issuer=issuer[:500],
        valid_from=_cert_not_before(cert),
        valid_to=_cert_not_after(cert),
        fingerprint_sha256=fingerprint,
        serial_number=format(cert.serial_number, "x"),
        subject=subject[:500],
        sans=sans,
        is_lets_encrypt=is_le,
    )


def try_parse_ssl_certificate(raw: bytes, *, preferred_name: str = "") -> ParsedSslCertificate | None:
    try:
        return parse_ssl_certificate(raw, preferred_name=preferred_name)
    except HTTPException:
        return None
