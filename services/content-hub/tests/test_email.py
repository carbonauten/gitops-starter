from unittest.mock import MagicMock


def test_resend_sends_invite_email(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "noreply@carbonauten.com")
    from app.config import get_settings

    get_settings.cache_clear()

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_post = MagicMock(return_value=mock_response)
    monkeypatch.setattr("app.email_service.httpx.post", mock_post)

    from app.email_service import send_invite_email

    sent = send_invite_email(
        to_email="new@example.com",
        invite_url="https://app.carbonauten.com/invite/token",
        role_label="Redakteur",
        invited_by_name="Admin",
        expires_days=7,
    )

    assert sent is True
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert call_kwargs[0][0] == "https://api.resend.com/emails"
    assert call_kwargs[1]["json"]["to"] == ["new@example.com"]
    get_settings.cache_clear()


def test_resend_preferred_over_smtp(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.setenv("SMTP_HOST", "smtp.office365.com")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "noreply@carbonauten.com")
    from app.config import get_settings

    get_settings.cache_clear()

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_post = MagicMock(return_value=mock_response)
    mock_smtp = MagicMock(return_value=True)
    monkeypatch.setattr("app.email_service.httpx.post", mock_post)
    monkeypatch.setattr("app.email_service._send_via_smtp", mock_smtp)

    from app.email_service import send_invite_email

    send_invite_email(
        to_email="new@example.com",
        invite_url="https://app.carbonauten.com/invite/token",
        role_label="Redakteur",
        invited_by_name="Admin",
        expires_days=7,
    )

    mock_post.assert_called_once()
    mock_smtp.assert_not_called()
    get_settings.cache_clear()


def test_health_reports_resend_provider(client, monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "noreply@carbonauten.com")
    from app.config import get_settings

    get_settings.cache_clear()
    response = client.get("/api/health")
    payload = response.json()
    assert payload["email_provider"] == "resend"
    assert payload["email_delivery_configured"] is True
    get_settings.cache_clear()
