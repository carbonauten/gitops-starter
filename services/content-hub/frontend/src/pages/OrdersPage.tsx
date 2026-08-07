import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { fetchAdminOrders, formatMoney, adminOrderInvoiceUrl, updateAdminOrderStatus, type ShopOrder } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";

const STATUSES = ["awaiting_payment", "paid", "fulfilled", "cancelled", "pending", "returned"] as const;
const CARRIERS = ["dhl", "dpd", "ups", "hermes", "gls", "deutsche_post", "other"] as const;

type ShippingDraft = {
  shipping_carrier: string;
  tracking_number: string;
  tracking_url: string;
};

export function OrdersPage() {
  const { t, i18n } = useTranslation();
  const [orders, setOrders] = useState<ShopOrder[]>([]);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busyId, setBusyId] = useState("");
  const [fulfillId, setFulfillId] = useState("");
  const [drafts, setDrafts] = useState<Record<string, ShippingDraft>>({});

  function draftFor(order: ShopOrder): ShippingDraft {
    return (
      drafts[order.id] || {
        shipping_carrier: order.shipping_carrier || "dhl",
        tracking_number: order.tracking_number || "",
        tracking_url: order.tracking_url || "",
      }
    );
  }

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

  async function changeStatus(order: ShopOrder, next: string, shipping?: ShippingDraft) {
    setBusyId(order.id);
    setError("");
    setNotice("");
    try {
      await updateAdminOrderStatus(order.id, next, shipping);
      setFulfillId("");
      setNotice(
        next === "fulfilled"
          ? t("orders.fulfilledNotice")
          : next === "cancelled"
            ? t("orders.cancelledNotice")
            : t("orders.updatedNotice"),
      );
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
      {notice ? <p className="success-text">{notice}</p> : null}
      {!loading && orders.length === 0 ? <EmptyState message={t("orders.empty")} icon="◈" /> : null}

      <div className="list-stack">
        {orders.map((order) => {
          const draft = draftFor(order);
          const showFulfillForm = fulfillId === order.id || order.status === "fulfilled";
          return (
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
              {order.tracking_number || order.tracking_url ? (
                <p className="muted">
                  {t("orders.tracking")}: {order.shipping_carrier || "—"} · {order.tracking_number || "—"}
                  {order.tracking_url ? (
                    <>
                      {" · "}
                      <a href={order.tracking_url} target="_blank" rel="noreferrer">
                        {t("orders.trackLink")}
                      </a>
                    </>
                  ) : null}
                </p>
              ) : null}

              {showFulfillForm && order.status !== "cancelled" && order.status !== "returned" ? (
                <div className="order-ship-form">
                  <label>
                    {t("orders.carrier")}
                    <select
                      value={draft.shipping_carrier}
                      onChange={(event) =>
                        setDrafts((current) => ({
                          ...current,
                          [order.id]: { ...draft, shipping_carrier: event.target.value },
                        }))
                      }
                    >
                      {CARRIERS.map((item) => (
                        <option key={item} value={item}>
                          {t(`orders.carriers.${item}`)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    {t("orders.trackingNumber")}
                    <input
                      value={draft.tracking_number}
                      onChange={(event) =>
                        setDrafts((current) => ({
                          ...current,
                          [order.id]: { ...draft, tracking_number: event.target.value },
                        }))
                      }
                      placeholder="00340…"
                    />
                  </label>
                  <label>
                    {t("orders.trackingUrl")}
                    <input
                      value={draft.tracking_url}
                      onChange={(event) =>
                        setDrafts((current) => ({
                          ...current,
                          [order.id]: { ...draft, tracking_url: event.target.value },
                        }))
                      }
                      placeholder="https://…"
                    />
                  </label>
                </div>
              ) : null}

              <div className="list-card-actions">
                <a href={adminOrderInvoiceUrl(order.id)} className="ghost-button link-button" target="_blank" rel="noreferrer">
                  {t("orders.downloadInvoice")}
                </a>
                {order.status !== "paid" && order.status !== "fulfilled" && order.status !== "returned" ? (
                  <button
                    type="button"
                    className="ghost-button"
                    disabled={busyId === order.id}
                    onClick={() => void changeStatus(order, "paid")}
                  >
                    {t("orders.markPaid")}
                  </button>
                ) : null}
                {order.status !== "fulfilled" && order.status !== "cancelled" && order.status !== "returned" ? (
                  fulfillId === order.id ? (
                    <>
                      <button
                        type="button"
                        className="primary-button"
                        disabled={busyId === order.id}
                        onClick={() => void changeStatus(order, "fulfilled", draft)}
                      >
                        {t("orders.confirmShip")}
                      </button>
                      <button type="button" className="ghost-button" onClick={() => setFulfillId("")}>
                        {t("common.cancel")}
                      </button>
                    </>
                  ) : (
                    <button type="button" className="primary-button" onClick={() => setFulfillId(order.id)}>
                      {t("orders.markFulfilled")}
                    </button>
                  )
                ) : null}
                {order.status === "fulfilled" ? (
                  <button
                    type="button"
                    className="ghost-button"
                    disabled={busyId === order.id}
                    onClick={() => void changeStatus(order, "fulfilled", draft)}
                  >
                    {t("orders.saveTracking")}
                  </button>
                ) : null}
                {order.status !== "cancelled" && order.status !== "returned" ? (
                  <button
                    type="button"
                    className="ghost-button"
                    disabled={busyId === order.id}
                    onClick={() => void changeStatus(order, "cancelled")}
                  >
                    {t("orders.markCancelled")}
                  </button>
                ) : null}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
