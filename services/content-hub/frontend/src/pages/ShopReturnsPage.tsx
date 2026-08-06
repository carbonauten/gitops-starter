import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  fetchAdminShopReturns,
  formatMoney,
  resolveAdminShopReturn,
  type ShopReturn,
} from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";

const STATUSES = ["requested", "approved", "rejected", "completed"] as const;

export function ShopReturnsPage() {
  const { t, i18n } = useTranslation();
  const [items, setItems] = useState<ShopReturn[]>([]);
  const [status, setStatus] = useState("requested");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [adminNote, setAdminNote] = useState<Record<string, string>>({});
  const [busyId, setBusyId] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      setItems(await fetchAdminShopReturns(status || undefined));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [status]);

  async function resolve(item: ShopReturn, next: "approved" | "rejected" | "completed") {
    setBusyId(item.id);
    setError("");
    setNotice("");
    try {
      await resolveAdminShopReturn(item.id, {
        status: next,
        admin_note: adminNote[item.id] || "",
      });
      setNotice(t("shopReturns.resolved", { status: t(`shopReturns.statusValues.${next}`) }));
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusyId("");
    }
  }

  return (
    <section className="page">
      <header className="page-header row-header">
        <div>
          <h1>{t("shopReturns.title")}</h1>
          <p className="muted">{t("shopReturns.subtitle")}</p>
        </div>
      </header>

      <div className="toolbar">
        <select value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="">{t("shopReturns.allStatuses")}</option>
          {STATUSES.map((item) => (
            <option key={item} value={item}>
              {t(`shopReturns.statusValues.${item}`)}
            </option>
          ))}
        </select>
      </div>

      {loading ? <LoadingState /> : null}
      {error ? <p className="error-text">{error}</p> : null}
      {notice ? <p className="success-text">{notice}</p> : null}
      {!loading && items.length === 0 ? <EmptyState message={t("shopReturns.empty")} icon="↩" /> : null}

      <div className="list-stack">
        {items.map((item) => (
          <article key={item.id} className="list-card">
            <div className="list-card-title-row">
              <strong>{item.return_number}</strong>
              <span className="workflow-badge workflow-badge-review">
                {t(`shopReturns.statusValues.${item.status}`, { defaultValue: item.status })}
              </span>
            </div>
            <p>
              {item.order_number} · {item.customer_name} · {item.customer_email}
            </p>
            <p className="muted">
              {formatMoney(item.order_total_cents || 0, item.order_currency || "EUR", i18n.language)} ·{" "}
              {t(`shopReturns.reasons.${item.reason}`, { defaultValue: item.reason })}
              {item.credits_earned ? ` · CO₂ ${item.credits_earned}` : ""}
            </p>
            {item.customer_note ? <p>{item.customer_note}</p> : null}
            {item.status === "requested" || item.status === "approved" ? (
              <>
                <label>
                  {t("shopReturns.adminNote")}
                  <textarea
                    rows={2}
                    value={adminNote[item.id] || item.admin_note || ""}
                    onChange={(event) =>
                      setAdminNote((current) => ({ ...current, [item.id]: event.target.value }))
                    }
                  />
                </label>
                <div className="list-card-actions">
                  {item.status === "requested" ? (
                    <button
                      type="button"
                      className="ghost-button"
                      disabled={busyId === item.id}
                      onClick={() => void resolve(item, "approved")}
                    >
                      {t("shopReturns.approve")}
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="primary-button"
                    disabled={busyId === item.id}
                    onClick={() => void resolve(item, "completed")}
                  >
                    {t("shopReturns.complete")}
                  </button>
                  <button
                    type="button"
                    className="ghost-button"
                    disabled={busyId === item.id}
                    onClick={() => void resolve(item, "rejected")}
                  >
                    {t("shopReturns.reject")}
                  </button>
                </div>
              </>
            ) : (
              <p className="muted">
                {item.admin_note || "—"} · CO₂ −{item.credits_reversed} ·{" "}
                {item.inventory_restored ? t("shopReturns.stockRestored") : t("shopReturns.stockNotRestored")}
              </p>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
