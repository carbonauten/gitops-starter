import { Navigate, Route, Routes } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { Layout } from "./components/Layout";
import { MasterRoute } from "./components/MasterRoute";
import { useAuth } from "./hooks/useAuth";
import { ArticleEditorPage } from "./pages/ArticleEditorPage";
import { ArticlesPage } from "./pages/ArticlesPage";
import { CertificateEditorPage } from "./pages/CertificateEditorPage";
import { CertificatesPage } from "./pages/CertificatesPage";
import { DashboardPage } from "./pages/DashboardPage";
import { FilesPage } from "./pages/FilesPage";
import { LoginPage } from "./pages/LoginPage";
import { AcceptInvitePage } from "./pages/AcceptInvitePage";
import { PublishPage } from "./pages/PublishPage";
import { AuditLogPage } from "./pages/AuditLogPage";
import { WorkflowPage } from "./pages/WorkflowPage";
import { UsersAdminPage } from "./pages/UsersAdminPage";
import { SearchPage } from "./pages/SearchPage";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { t } = useTranslation();
  const { user, loading } = useAuth();

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

  return <Layout>{children}</Layout>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/invite/:token" element={<AcceptInvitePage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/search"
        element={
          <ProtectedRoute>
            <SearchPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/articles/new"
        element={
          <ProtectedRoute>
            <ArticleEditorPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/articles/:id/edit"
        element={
          <ProtectedRoute>
            <ArticleEditorPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/articles"
        element={
          <ProtectedRoute>
            <ArticlesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/files"
        element={
          <ProtectedRoute>
            <FilesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/certificates/new"
        element={
          <ProtectedRoute>
            <CertificateEditorPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/certificates/:id/edit"
        element={
          <ProtectedRoute>
            <CertificateEditorPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/certificates"
        element={
          <ProtectedRoute>
            <CertificatesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/users"
        element={
          <MasterRoute>
            <UsersAdminPage />
          </MasterRoute>
        }
      />
      <Route
        path="/publish"
        element={
          <ProtectedRoute>
            <PublishPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/workflow"
        element={
          <ProtectedRoute>
            <WorkflowPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/audit"
        element={
          <MasterRoute>
            <AuditLogPage />
          </MasterRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
