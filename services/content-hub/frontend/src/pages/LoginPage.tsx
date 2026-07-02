import { FormEvent, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { useAuth } from "../hooks/useAuth";
import { BrandLogo } from "../components/BrandLogo";
import { LanguageSwitch } from "../components/LanguageSwitch";

export function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user, loading, microsoftAuthEnabled, signInWithPassword, signInWithMicrosoft } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  if (!loading && user) {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await signInWithPassword(email.trim(), password);
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
        <h1 className="login-title">{t("auth.welcome")}</h1>
        <p className="muted login-description">{t("auth.description")}</p>

        <form className="login-form" onSubmit={(event) => void handleSubmit(event)}>
          <label className="form-field">
            <span>{t("auth.email")}</span>
            <input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>
          <label className="form-field">
            <span>{t("auth.password")}</span>
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>
          {error ? <p className="error-text">{error}</p> : null}
          <button type="submit" className="primary-button login-submit" disabled={loading || submitting}>
            {submitting ? t("common.loading") : t("auth.signIn")}
          </button>
        </form>

        {microsoftAuthEnabled ? (
          <button
            type="button"
            className="ghost-button login-microsoft"
            onClick={signInWithMicrosoft}
            disabled={loading || submitting}
          >
            {t("auth.signInMicrosoft")}
          </button>
        ) : null}
      </div>
    </div>
  );
}
