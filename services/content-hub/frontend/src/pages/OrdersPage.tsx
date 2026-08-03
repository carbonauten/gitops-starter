import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { fetchAdminOrders, formatMoney, updateAdminOrderStatus, type ShopOrder } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";

const STATUSES = ["awaiting_payment", "paid", "fulfilled", "cancelled", "pending"] as const;

export function OrdersPage() {
  const { t, i18n } = useTranslation();
  const [orders, setOrders] = useState<ShopOrder[]>([]);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      setOrders(await fetchAdminOrders(status || undefined));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [status]);

  async function changeStatus(order: ShopOrder, next: string) {
    await updateAdminOrderStatus(order.id, next);
    await load();
  }

  return (
    <section className="page">
      <header className="page-header row-header">
        <div>
          <h1>{t("orders.title")}</h1>
          <p className="muted">{t("orders.subtitle")}</p>
        </div>
      </header>

      <div className="toolbar">
        <select value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="">{t("orders.allStatuses")}</option>
          {STATUSES.map((item) => (
            <option key={item} value={item}>
              {t(`shop.statusValues.${item}`, { defaultValue: item })}
            </option>
          ))}
        </select>
      </div>

      {loading ? <LoadingState /> : null}
      {error ? <p className="error-text">{error}</p> : null}
      {!loading && orders.length === 0 ? <EmptyState message={t("orders.empty")} icon="◈" /> : null}

      <div className="list-stack">
        {orders.map((order) => (
          <article key={order.id} className="list-card">
            <div className="list-card-title-row">
              <strong>{order.order_number}</strong>
              <span className="workflow-badge workflow-badge-review">
                {t(`shop.statusValues.${order.status}`, { defaultValue: order.status })}
              </span>
            </div>
            <p>
              {order.customer_name} · {order.customer_email}
            </p>
            <p className="muted">
              {formatMoney(order.total_cents, order.currency, i18n.language)} · {order.payment_method} ·{" "}
              {order.postal_code} {order.city}
            </p>
            <ul className="muted">
              {order.items.map((item) => (
                <li key={item.id}>
                  {item.quantity}× {item.product_name}
                </li>
              ))}
            </ul>
            <div className="list-card-actions">
              {order.status !== "paid" ? (
                <button type="button" className="ghost-button" onClick={() => void changeStatus(order, "paid")}>
                  {t("orders.markPaid")}
                </button>
              ) : null}
              {order.status !== "fulfilled" ? (
                <button type="button" className="primary-button" onClick={() => void changeStatus(order, "fulfilled")}>
                  {t("orders.markFulfilled")}
                </button>
              ) : null}
              {order.status !== "cancelled" ? (
                <button type="button" className="ghost-button" onClick={() => void changeStatus(order, "cancelled")}>
                  {t("orders.markCancelled")}
                </button>
              ) : null}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
