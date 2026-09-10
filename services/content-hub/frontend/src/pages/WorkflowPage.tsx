import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import {
  approveArticle,
  approveCertificateRenewal,
  fetchWorkflowPending,
  rejectArticle,
  rejectCertificateRenewal,
  type WorkflowPending,
} from "../api/client";
import { ArticleStatusBadge } from "../components/ArticleStatusBadge";
import { CertificateStatusBadge } from "../components/CertificateStatusBadge";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";
import { usePermissions } from "../hooks/usePermissions";

export function WorkflowPage() {
  const { t } = useTranslation();
  const { canApprove, canApproveCertificates } = usePermissions();
  const [pending, setPending] = useState<WorkflowPending | null>(null);
  const [loading, setLoading] = useState(true);
  const [scheduleAt, setScheduleAt] = useState<Record<string, string>>({});
  const [rejectComment, setRejectComment] = useState<Record<string, string>>({});
  const [busyId, setBusyId] = useState("");
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    try {
      setPending(await fetchWorkflowPending());
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function handleApproveArticle(id: string) {
    setBusyId(id);
    setError("");
    try {
      const value = scheduleAt[id];
      await approveArticle(id, value ? new Date(value).toISOString() : null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusyId("");
    }
  }

  async function handleRejectArticle(id: string) {
    setBusyId(id);
    setError("");
    try {
      await rejectArticle(id, rejectComment[id] || "");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusyId("");
    }
  }

  async function handleApproveRenewal(id: string) {
    setBusyId(id);
    setError("");
    try {
      await approveCertificateRenewal(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusyId("");
    }
  }

  async function handleRejectRenewal(id: string) {
    setBusyId(id);
    setError("");
    try {
      await rejectCertificateRenewal(id, rejectComment[id] || "");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusyId("");
    }
  }

  const isEmpty =
    !pending ||
    (pending.articles_in_review.length === 0 &&
      pending.articles_scheduled.length === 0 &&
      pending.certificate_renewals_pending.length === 0);

  return (
    <section className="page">
      <header className="page-header">
        <h1>{t("workflow.title")}</h1>
        <p className="muted">{t("workflow.subtitle")}</p>
      </header>

      {loading ? <LoadingState /> : null}
      {error ? <p className="error-text">{error}</p> : null}
      {!loading && isEmpty ? <EmptyState message={t("workflow.empty")} icon="✓" /> : null}

      {pending && pending.articles_in_review.length > 0 ? (
        <div className="section-block">
          <h2>{t("workflow.articlesInReview")}</h2>
          <div className="list-stack">
            {pending.articles_in_review.map((article) => (
              <article key={article.id} className="list-card">
                <div>
                  <div className="list-card-title-row">
                    <h3>{article.title || t("articles.untitled")}</h3>
                    <ArticleStatusBadge status="review" />
                  </div>
                  <p className="muted">
                    {article.author_name} · {new Date(article.updated_at).toLocaleString()}
                  </p>
                </div>
                {canApprove ? (
                  <div className="list-card-actions workflow-actions">
                    <input
                      type="datetime-local"
                      value={scheduleAt[article.id] || ""}
                      disabled={busyId === article.id}
                      onChange={(event) =>
                        setScheduleAt((current) => ({ ...current, [article.id]: event.target.value }))
                      }
                      aria-label={t("workflow.scheduleAt")}
                    />
                    <button
                      type="button"
                      className="primary-button"
                      disabled={busyId === article.id}
                      onClick={() => void handleApproveArticle(article.id)}
                    >
                      {busyId === article.id
                        ? t("common.loading")
                        : scheduleAt[article.id]
                          ? t("workflow.approveSchedule")
                          : t("workflow.approve")}
                    </button>
                    <input
                      type="text"
                      placeholder={t("workflow.rejectComment")}
                      value={rejectComment[article.id] || ""}
                      disabled={busyId === article.id}
                      onChange={(event) =>
                        setRejectComment((current) => ({ ...current, [article.id]: event.target.value }))
                      }
                    />
                    <button
                      type="button"
                      className="ghost-button danger"
                      disabled={busyId === article.id}
                      onClick={() => void handleRejectArticle(article.id)}
                    >
                      {busyId === article.id ? t("common.loading") : t("workflow.reject")}
                    </button>
                    <Link to={`/articles/${article.id}/edit`} className="ghost-button link-button">
                      {t("articles.edit")}
                    </Link>
                  </div>
                ) : null}
              </article>
            ))}
          </div>
        </div>
      ) : null}

      {pending && pending.articles_scheduled.length > 0 ? (
        <div className="section-block">
          <h2>{t("workflow.articlesScheduled")}</h2>
          <div className="list-stack">
            {pending.articles_scheduled.map((article) => (
              <article key={article.id} className="list-card">
                <div>
                  <div className="list-card-title-row">
                    <h3>{article.title || t("articles.untitled")}</h3>
                    <ArticleStatusBadge status="scheduled" />
                  </div>
                  <p className="muted">
                    {t("articles.scheduledAt")}:{" "}
                    {article.scheduled_publish_at ? new Date(article.scheduled_publish_at).toLocaleString() : "—"}
                  </p>
                </div>
              </article>
            ))}
          </div>
        </div>
      ) : null}

      {pending && pending.certificate_renewals_pending.length > 0 ? (
        <div className="section-block">
          <h2>{t("workflow.renewalsPending")}</h2>
          <div className="list-stack">
            {pending.certificate_renewals_pending.map((certificate) => (
              <article key={certificate.id} className="list-card">
                <div>
                  <div className="list-card-title-row">
                    <h3>{certificate.name}</h3>
                    <CertificateStatusBadge status="renewal" />
                  </div>
                  <p className="muted">
                    {certificate.responsible_name} · {new Date(certificate.updated_at).toLocaleString()}
                  </p>
                </div>
                {canApproveCertificates ? (
                  <div className="list-card-actions workflow-actions">
                    <button
                      type="button"
                      className="primary-button"
                      disabled={busyId === certificate.id}
                      onClick={() => void handleApproveRenewal(certificate.id)}
                    >
                      {busyId === certificate.id ? t("common.loading") : t("workflow.approveRenewal")}
                    </button>
                    <button
                      type="button"
                      className="ghost-button danger"
                      disabled={busyId === certificate.id}
                      onClick={() => void handleRejectRenewal(certificate.id)}
                    >
                      {busyId === certificate.id ? t("common.loading") : t("workflow.rejectRenewal")}
                    </button>
                    <Link to={`/certificates/${certificate.id}/edit`} className="ghost-button link-button">
                      {t("certificates.edit")}
                    </Link>
                  </div>
                ) : null}
              </article>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}
