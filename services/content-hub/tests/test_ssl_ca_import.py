from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def _make_pem(cn: str = "ssl.example.com", issuer_org: str = "Test CA", days: int = 90) -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, issuer_org),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, issuer_org),
        ]
    )
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=days))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(cn)]), critical=False)
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM)


def test_parse_ssl_endpoint(auth_client):
    pem = _make_pem("api.carbonauten.com", "Let's Encrypt")
    response = auth_client.post(
        "/api/certificates/parse-ssl",
        files={"upload": ("api.pem", BytesIO(pem), "application/x-pem-file")},
    )
    assert response.status_code == 200
    parsed = response.json()["parsed"]
    assert parsed["name"] == "api.carbonauten.com"
    assert parsed["category"] == "ssl"
    assert parsed["is_lets_encrypt"] is True
    assert parsed["fingerprint_sha256"]
    assert parsed["valid_from"]
    assert parsed["valid_to"]


def test_import_ssl_creates_and_upserts(auth_client):
    pem = _make_pem("shop.fuckco2.shop", "Let's Encrypt")
    first = auth_client.post(
        "/api/certificates/import-ssl",
        files={"upload": ("shop.pem", BytesIO(pem), "application/x-pem-file")},
    )
    assert first.status_code == 201
    payload = first.json()
    assert payload["created"] is True
    cert = payload["certificate"]
    assert cert["category"] == "ssl"
    assert cert["name"] == "shop.fuckco2.shop"
    assert cert["fingerprint"]
    assert cert["external_source"] == "ssl_file"
    cert_id = cert["id"]

    second = auth_client.post(
        "/api/certificates/import-ssl",
        files={"upload": ("shop-again.pem", BytesIO(pem), "application/x-pem-file")},
    )
    assert second.status_code == 201
    assert second.json()["created"] is False
    assert second.json()["certificate"]["id"] == cert_id

    listing = auth_client.get("/api/certificates", params={"category": "ssl"})
    assert len(listing.json()["certificates"]) == 1


def test_ca_sync_status_and_key_vault_mock(auth_client, monkeypatch):
    monkeypatch.setenv("KEY_VAULT_MOCK_MODE", "true")
    from app.config import get_settings

    get_settings.cache_clear()

    status = auth_client.get("/api/certificates/ca-sync/status")
    assert status.status_code == 200
    assert status.json()["ssl_file_import"] is True
    assert status.json()["key_vault_mock"] is True

    sync = auth_client.post("/api/certificates/ca-sync/key-vault")
    assert sync.status_code == 200
    body = sync.json()
    assert body["created"] >= 1
    assert body["mock"] is True

    listing = auth_client.get("/api/certificates", params={"category": "ssl"})
    assert len(listing.json()["certificates"]) >= 1
    get_settings.cache_clear()


def test_letsencrypt_dir_sync(auth_client, monkeypatch, tmp_path):
    live = tmp_path / "live"
    domain = live / "www.example.com"
    domain.mkdir(parents=True)
    (domain / "cert.pem").write_bytes(_make_pem("www.example.com", "Let's Encrypt"))

    monkeypatch.setenv("LETSENCRYPT_LIVE_DIR", str(live))
    from app.config import get_settings

    get_settings.cache_clear()

    sync = auth_client.post("/api/certificates/ca-sync/letsencrypt")
    assert sync.status_code == 200
    assert sync.json()["created"] == 1

    listing = auth_client.get("/api/certificates", params={"category": "ssl"})
    names = [item["name"] for item in listing.json()["certificates"]]
    assert "www.example.com" in names
    get_settings.cache_clear()


def test_invalid_ssl_rejected(auth_client):
    response = auth_client.post(
        "/api/certificates/import-ssl",
        files={"upload": ("bad.pem", BytesIO(b"not-a-cert"), "text/plain")},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_ssl_certificate"
