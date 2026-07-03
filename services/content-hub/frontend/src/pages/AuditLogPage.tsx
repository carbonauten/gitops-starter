import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { fetchAuditLog, type AuditEntry } from "../api/client";

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

      {loading ? <p>{t("common.loading")}</p> : null}
      {!loading && entries.length === 0 ? <div className="empty-state">{t("audit.empty")}</div> : null}

      {!loading && entries.length > 0 ? (
        <div className="table-wrap">
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
                  <td>{entry.action}</td>
                  <td>
                    {entry.entity_type}/{entry.entity_id.slice(0, 8)}
                  </td>
                  <td>
                    <code>{JSON.stringify(entry.details)}</code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}
