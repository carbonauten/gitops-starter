import { Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { useAuth } from "../hooks/useAuth";
import { usePermissions } from "../hooks/usePermissions";
import { Layout } from "./Layout";

export function MasterRoute({ children }: { children: React.ReactNode }) {
  const { t } = useTranslation();
  const { user, loading } = useAuth();
  const { isItMaster } = usePermissions();

  if (loading) {
    return (
      <div className="center-screen" style={{ fontSize: "1.1rem", color: "#334155" }}>
        {t("common.loading")}
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (!isItMaster) {
    return <Navigate to="/" replace />;
  }

  return <Layout>{children}</Layout>;
}
