import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import {
  certificatesAuditExportUrl,
  certificatesExportUrl,
  deleteCertificate,
  fetchCertificates,
  type Certificate,
} from "../api/client";
import { CertificateStatusBadge } from "../components/CertificateStatusBadge";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";
import { usePermissions } from "../hooks/usePermissions";

const CATEGORIES = ["compliance", "product", "training", "ssl"] as const;
const STATUSES = ["valid", "expiring", "expired", "renewal"] as const;

export function CertificatesPage() {
  const { t } = useTranslation();
  const { canEdit } = usePermissions();
  const [certificates, setCertificates] = useState<Certificate[]>([]);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const items = await fetchCertificates(
        query || undefined,
        category || undefined,
        status || undefined,
      );
      setCertificates(items);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [query, category, status]);

  async function handleDelete(id: string) {
    if (!window.confirm(t("certificates.confirmDelete"))) return;
    await deleteCertificate(id);
    await load();
  }

  const categoryCounts = CATEGORIES.map((item) => ({
    key: item,
    label: t(`certificates.categories.${item}`),
    count: certificates.filter((certificate) => certificate.category === item).length,
  }));

  return (
    <section className="page">
      <header className="page-header row-header">
        <div>
          <h1>{t("certificates.title")}</h1>
          <p className="muted">{t("certificates.subtitle")}</p>
        </div>
        <div className="header-actions">
          <a href={certificatesExportUrl()} className="ghost-button link-button">
            {t("certificates.export")}
          </a>
          <a href={certificatesAuditExportUrl()} className="ghost-button link-button">
            {t("certificates.auditExport")}
          </a>
          {canEdit ? (
            <Link to="/certificates/new" className="primary-button link-button">
              {t("certificates.new")}
            </Link>
          ) : null}
        </div>
      </header>

      <div className="card-grid compact-grid">
        {categoryCounts.map((item) => (
          <article key={item.key} className="stat-card">
            <p className="stat-label">{item.label}</p>
            <p className="stat-value">{item.count}</p>
          </article>
        ))}
      </div>

      <div className="toolbar">
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t("certificates.searchPlaceholder")}
        />
        <select value={category} onChange={(event) => setCategory(event.target.value)}>
          <option value="">{t("certificates.allCategories")}</option>
          {CATEGORIES.map((item) => (
            <option key={item} value={item}>
              {t(`certificates.categories.${item}`)}
            </option>
          ))}
        </select>
        <select value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="">{t("certificates.allStatuses")}</option>
          {STATUSES.map((item) => (
            <option key={item} value={item}>
              {t(`certificates.status.${item}`)}
            </option>
          ))}
        </select>
      </div>

      {loading ? <LoadingState /> : null}
      {error ? <p className="error-text">{error}</p> : null}
      {!loading && certificates.length === 0 ? (
        <EmptyState message={t("certificates.empty")} icon="◎" />
      ) : null}

      <div className="list-stack">
        {certificates.map((certificate) => (
          <article key={certificate.id} className="list-card">
            <div>
              <div className="list-card-title-row">
                <h2>{certificate.name}</h2>
                <CertificateStatusBadge status={certificate.status} />
              </div>
              <p className="muted">
                {t(`certificates.categories.${certificate.category}`)} · {certificate.issuer || t("certificates.noIssuer")}
              </p>
              {certificate.parent_name ? (
                <p className="muted">
                  {t("certificates.parent")}: {certificate.parent_name}
                </p>
              ) : null}
              {(certificate.children?.length || 0) > 0 ? (
                <p className="muted">
                  {t("certificates.childrenCount", { count: certificate.children?.length || 0 })}
                </p>
              ) : null}
              <p className="muted">
                {t("certificates.validUntil")}: {certificate.valid_to}
                {certificate.days_until_expiry >= 0
                  ? ` · ${t("certificates.daysLeft", { count: certificate.days_until_expiry })}`
                  : ` · ${t("certificates.overdue", { count: Math.abs(certificate.days_until_expiry) })}`}
              </p>
              {certificate.responsible_name ? (
                <p className="muted">
                  {t("certificates.responsible")}: {certificate.responsible_name}
                </p>
              ) : null}
            </div>
            <div className="list-card-actions">
              {canEdit ? (
                <>
                  <Link to={`/certificates/${certificate.id}/edit`} className="ghost-button link-button">
                    {t("certificates.edit")}
                  </Link>
                  <button type="button" className="ghost-button danger" onClick={() => void handleDelete(certificate.id)}>
                    {t("certificates.delete")}
                  </button>
                </>
              ) : null}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
