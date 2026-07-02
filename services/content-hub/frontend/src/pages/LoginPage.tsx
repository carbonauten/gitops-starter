import { Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { useAuth } from "../hooks/useAuth";
import { BrandLogo } from "../components/BrandLogo";
import { LanguageSwitch } from "../components/LanguageSwitch";

export function LoginPage() {
  const { t } = useTranslation();
  const { user, loading, signIn } = useAuth();

  if (!loading && user) {
    return <Navigate to="/" replace />;
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
        <button type="button" className="primary-button" onClick={signIn} disabled={loading}>
          {loading ? t("common.loading") : t("auth.signIn")}
        </button>
      </div>
    </div>
  );
}
