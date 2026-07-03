import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { fetchAuditLog, type AuditEntry } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";

function actionBadgeClass(action: string): string {
  if (action.includes("delete") || action.includes("reject")) {
    return "workflow-badge workflow-badge-rejected";
  }
  if (action.includes("approve") || action.includes("publish") || action.includes("create")) {
    return "workflow-badge workflow-badge-published";
  }
  if (action.includes("update") || action.includes("submit")) {
    return "workflow-badge workflow-badge-review";
  }
  return "workflow-badge workflow-badge-draft";
}

export function AuditLogPage() {
  const { t } = useTranslation();
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      try {
        setEntries(await fetchAuditLog());
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <section className="page">
      <header className="page-header">
        <h1>{t("audit.title")}</h1>
        <p className="muted">{t("audit.subtitle")}</p>
      </header>

      {loading ? <LoadingState /> : null}
      {!loading && entries.length === 0 ? <EmptyState message={t("audit.empty")} icon="≡" /> : null}

      {!loading && entries.length > 0 ? (
        <>
          <div className="table-wrap audit-table-desktop">
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("audit.columns.time")}</th>
                  <th>{t("audit.columns.actor")}</th>
                  <th>{t("audit.columns.action")}</th>
                  <th>{t("audit.columns.entity")}</th>
                  <th>{t("audit.columns.details")}</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <tr key={entry.id}>
                    <td>{entry.created_at}</td>
                    <td>{entry.actor_name}</td>
                    <td>
                      <span className={actionBadgeClass(entry.action)}>{entry.action}</span>
                    </td>
                    <td>
                      {entry.entity_type}/{entry.entity_id.slice(0, 8)}
                    </td>
                    <td>
                      <code className="audit-details">{JSON.stringify(entry.details)}</code>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="audit-card-list">
            {entries.map((entry) => (
              <article key={entry.id} className="audit-card">
                <div className="list-card-title-row">
                  <span className={actionBadgeClass(entry.action)}>{entry.action}</span>
                  <span className="muted audit-card-time">{entry.created_at}</span>
                </div>
                <p>
                  <strong>{entry.actor_name}</strong>
                </p>
                <p className="muted">
                  {entry.entity_type}/{entry.entity_id.slice(0, 8)}
                </p>
                <code className="audit-details">{JSON.stringify(entry.details)}</code>
              </article>
            ))}
          </div>
        </>
      ) : null}
    </section>
  );
}
