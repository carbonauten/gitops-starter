import { FormEvent, useEffect, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { acceptInvite, fetchInvite, type PublicInvite } from "../api/client";
import { BrandLogo } from "../components/BrandLogo";
import { LanguageSwitch } from "../components/LanguageSwitch";
import { useAuth } from "../hooks/useAuth";

export function AcceptInvitePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { token = "" } = useParams();
  const { user, loading, refresh } = useAuth();
  const [invite, setInvite] = useState<PublicInvite | null>(null);
  const [inviteLoading, setInviteLoading] = useState(true);
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) {
      setInviteLoading(false);
      setError(t("invite.invalid"));
      return;
    }

    void (async () => {
      try {
        const nextInvite = await fetchInvite(token);
        setInvite(nextInvite);
      } catch (err) {
        setError(err instanceof Error ? err.message : t("invite.invalid"));
      } finally {
        setInviteLoading(false);
      }
    })();
  }, [token, t]);

  if (!loading && user) {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !invite) {
      return;
    }
    if (password.length < 8) {
      setError(t("invite.passwordTooShort"));
      return;
    }
    if (password !== confirmPassword) {
      setError(t("invite.passwordMismatch"));
      return;
    }

    setSubmitting(true);
    setError("");
    try {
      await acceptInvite(token, name.trim(), password);
      await refresh();
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-screen">
      <div className="login-card">
        <div className="login-card-header">
          <BrandLogo size="lg" />
          <LanguageSwitch />
        </div>
        <h1 className="login-title">{t("invite.title")}</h1>

        {inviteLoading ? <p className="muted">{t("common.loading")}</p> : null}
        {error ? <p className="error-text">{error}</p> : null}

        {invite ? (
          <>
            <p className="muted login-description">
              {t("invite.description", {
                name: invite.invited_by_name,
                role: t(`users.roles.${invite.role}`),
              })}
            </p>
            <p className="invite-email">
              <strong>{invite.email}</strong>
              {invite.department_name ? (
                <span className="muted"> · {invite.department_name}</span>
              ) : null}
            </p>

            <form className="login-form" onSubmit={(event) => void handleSubmit(event)}>
              <label className="form-field">
                <span>{t("invite.name")}</span>
                <input
                  type="text"
                  autoComplete="name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  required
                />
              </label>
              <label className="form-field">
                <span>{t("invite.password")}</span>
                <input
                  type="password"
                  autoComplete="new-password"
                  value={password}
                  minLength={8}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                />
              </label>
              <label className="form-field">
                <span>{t("invite.confirmPassword")}</span>
                <input
                  type="password"
                  autoComplete="new-password"
                  value={confirmPassword}
                  minLength={8}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  required
                />
              </label>
              <button type="submit" className="primary-button login-submit" disabled={submitting}>
                {submitting ? t("common.loading") : t("invite.submit")}
              </button>
            </form>
          </>
        ) : null}
      </div>
    </div>
  );
}
