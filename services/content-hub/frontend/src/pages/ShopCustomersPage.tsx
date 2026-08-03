import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  adjustShopCustomerCredits,
  fetchShopCustomerAdmin,
  fetchShopCustomersAdmin,
  updateShopCustomerActive,
  type ShopCreditLedgerEntry,
  type ShopCustomer,
  type ShopOrder,
} from "../api/client";
import { usePermissions } from "../hooks/usePermissions";

export function ShopCustomersPage() {
  const { t, i18n } = useTranslation();
  const { isItMaster } = usePermissions();
  const [customers, setCustomers] = useState<ShopCustomer[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<{
    customer: ShopCustomer;
    ledger: ShopCreditLedgerEntry[];
    orders: ShopOrder[];
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [creditDelta, setCreditDelta] = useState("10");
  const [creditNote, setCreditNote] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      setCustomers(await fetchShopCustomersAdmin());
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    void (async () => {
      try {
        setDetail(await fetchShopCustomerAdmin(selectedId));
      } catch (err) {
        setError(err instanceof Error ? err.message : t("common.error"));
      }
    })();
  }, [selectedId, t]);

  async function handleActive(customer: ShopCustomer, isActive: boolean) {
    setBusyId(customer.id);
    try {
      await updateShopCustomerActive(customer.id, isActive);
      await load();
      if (selectedId === customer.id) {
        setDetail(await fetchShopCustomerAdmin(customer.id));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusyId(null);
    }
  }

  async function handleCredits() {
    if (!selectedId) return;
    const delta = Number(creditDelta);
    if (!Number.isFinite(delta) || delta === 0) return;
    setBusyId(selectedId);
    try {
      await adjustShopCustomerCredits(selectedId, delta, creditNote);
      setCreditNote("");
      await load();
      setDetail(await fetchShopCustomerAdmin(selectedId));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="page">
      <header className="page-header">
        <h1>{t("shopCustomers.title")}</h1>
        <p className="muted">{t("shopCustomers.subtitle")}</p>
      </header>

      {loading ? <p>{t("common.loading")}</p> : null}
      {error ? <p className="error-text">{error}</p> : null}

      {!loading && customers.length === 0 ? <p className="muted">{t("shopCustomers.empty")}</p> : null}

      {!loading && customers.length > 0 ? (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>{t("shopCustomers.columns.name")}</th>
                <th>{t("shopCustomers.columns.email")}</th>
                <th>{t("shopCustomers.columns.credits")}</th>
                <th>{t("shopCustomers.columns.status")}</th>
                <th>{t("shopCustomers.columns.lastLogin")}</th>
                <th>{t("departments.columns.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {customers.map((customer) => (
                <tr key={customer.id} className={selectedId === customer.id ? "row-selected" : undefined}>
                  <td>
                    <button type="button" className="linkish" onClick={() => setSelectedId(customer.id)}>
                      <strong>{customer.name}</strong>
                    </button>
                  </td>
                  <td>{customer.email}</td>
                  <td>{customer.co2_credit_balance}</td>
                  <td>{customer.is_active ? t("users.active") : t("users.platformAccess.off")}</td>
                  <td>
                    {customer.last_login_at
                      ? new Date(customer.last_login_at).toLocaleString(i18n.language)
                      : t("users.neverLoggedIn")}
                  </td>
                  <td>
                    {isItMaster ? (
                      <button
                        type="button"
                        className="ghost-button"
                        disabled={busyId === customer.id}
                        onClick={() => void handleActive(customer, !customer.is_active)}
                      >
                        {customer.is_active ? t("shopCustomers.disable") : t("shopCustomers.enable")}
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {detail ? (
        <div className="panel" style={{ marginTop: "1.5rem" }}>
          <h2>
            {detail.customer.name} · {detail.customer.co2_credit_balance} {t("shopCustomers.creditsUnit")}
          </h2>
          {isItMaster ? (
            <div className="employee-create-grid" style={{ marginBottom: "1rem" }}>
              <input
                type="number"
                value={creditDelta}
                onChange={(event) => setCreditDelta(event.target.value)}
                placeholder={t("shopCustomers.creditDelta")}
              />
              <input
                type="text"
                value={creditNote}
                onChange={(event) => setCreditNote(event.target.value)}
                placeholder={t("shopCustomers.creditNote")}
              />
              <button
                type="button"
                className="primary-button"
                disabled={busyId === detail.customer.id}
                onClick={() => void handleCredits()}
              >
                {t("shopCustomers.adjustCredits")}
              </button>
            </div>
          ) : null}
          <h3>{t("shopCustomers.ledger")}</h3>
          <ul>
            {detail.ledger.length === 0 ? <li className="muted">{t("shopCustomers.ledgerEmpty")}</li> : null}
            {detail.ledger.map((entry) => (
              <li key={entry.id}>
                {entry.delta_credits > 0 ? "+" : ""}
                {entry.delta_credits} · {entry.reason}
                {entry.note ? ` — ${entry.note}` : ""}
              </li>
            ))}
          </ul>
          <h3>{t("shopCustomers.orders")}</h3>
          <ul>
            {detail.orders.length === 0 ? <li className="muted">{t("orders.empty")}</li> : null}
            {detail.orders.map((order) => (
              <li key={order.id}>
                {order.order_number} · {order.status} · {(order.total_cents / 100).toFixed(2)} {order.currency}
                {order.credits_earned ? ` · +${order.credits_earned} CO₂` : ""}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
