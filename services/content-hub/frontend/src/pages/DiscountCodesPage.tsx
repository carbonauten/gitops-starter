import { FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  createDiscountCode,
  deleteDiscountCode,
  fetchDiscountCodes,
  formatMoney,
  updateDiscountCode,
  type DiscountCode,
} from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";

export function DiscountCodesPage() {
  const { t, i18n } = useTranslation();
  const [codes, setCodes] = useState<DiscountCode[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [code, setCode] = useState("");
  const [discountType, setDiscountType] = useState<"percent" | "fixed">("percent");
  const [percentValue, setPercentValue] = useState("10");
  const [amountValue, setAmountValue] = useState("5.00");
  const [minOrder, setMinOrder] = useState("0");
  const [maxRedemptions, setMaxRedemptions] = useState("");
  const [validFrom, setValidFrom] = useState("");
  const [validUntil, setValidUntil] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      setCodes(await fetchDiscountCodes());
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const created = await createDiscountCode({
        code,
        discount_type: discountType,
        percent_off_bps: discountType === "percent" ? Math.round(Number(percentValue) * 100) : undefined,
        amount_off_cents: discountType === "fixed" ? Math.round(Number(amountValue) * 100) : undefined,
        min_order_cents: Math.round(Number(minOrder || "0") * 100),
        max_redemptions: maxRedemptions ? Number(maxRedemptions) : undefined,
        valid_from: validFrom ? new Date(validFrom).toISOString() : null,
        valid_until: validUntil ? new Date(validUntil).toISOString() : null,
      });
      setNotice(t("discountCodes.created", { code: created.code }));
      setCode("");
      setPercentValue("10");
      setAmountValue("5.00");
      setMinOrder("0");
      setMaxRedemptions("");
      setValidFrom("");
      setValidUntil("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function handleToggleActive(entry: DiscountCode) {
    setBusy(true);
    setError("");
    try {
      await updateDiscountCode(entry.id, { is_active: !entry.is_active });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(entry: DiscountCode) {
    if (!window.confirm(t("discountCodes.confirmDelete", { code: entry.code }))) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await deleteDiscountCode(entry.id);
      setNotice(t("discountCodes.deleted", { code: entry.code }));
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  function describeValue(entry: DiscountCode): string {
    if (entry.discount_type === "percent") {
      return `${((entry.percent_off_bps || 0) / 100).toString()}%`;
    }
    return formatMoney(entry.amount_off_cents || 0, "EUR", i18n.language);
  }

  return (
    <section className="page">
      <header className="page-header">
        <h1>{t("discountCodes.title")}</h1>
        <p className="muted">{t("discountCodes.subtitle")}</p>
      </header>

      {error ? <p className="error-text">{error}</p> : null}
      {notice ? (
        <p className="success-text" role="status">
          {notice}
        </p>
      ) : null}

      <div className="integration-connect-block">
        <div className="integration-connect-header">
          <strong>{t("discountCodes.createTitle")}</strong>
        </div>
        <form className="entra-setup-form" onSubmit={(event) => void handleCreate(event)}>
          <label>
            {t("discountCodes.code")}
            <input
              value={code}
              onChange={(event) => setCode(event.target.value.toUpperCase())}
              placeholder="SOMMER10"
              required
              autoComplete="off"
            />
          </label>
          <label className="checkbox-row">
            <input
              type="radio"
              checked={discountType === "percent"}
              onChange={() => setDiscountType("percent")}
            />
            {t("discountCodes.typePercent")}
          </label>
          <label className="checkbox-row">
            <input type="radio" checked={discountType === "fixed"} onChange={() => setDiscountType("fixed")} />
            {t("discountCodes.typeFixed")}
          </label>
          {discountType === "percent" ? (
            <label>
              {t("discountCodes.percentOff")}
              <input
                type="number"
                min={1}
                max={100}
                step="0.01"
                value={percentValue}
                onChange={(event) => setPercentValue(event.target.value)}
                required
              />
            </label>
          ) : (
            <label>
              {t("discountCodes.amountOff")}
              <input
                type="number"
                min={0.01}
                step="0.01"
                value={amountValue}
                onChange={(event) => setAmountValue(event.target.value)}
                required
              />
            </label>
          )}
          <div className="row-actions">
            <label>
              {t("discountCodes.minOrder")}
              <input
                type="number"
                min={0}
                step="0.01"
                value={minOrder}
                onChange={(event) => setMinOrder(event.target.value)}
              />
            </label>
            <label>
              {t("discountCodes.maxRedemptions")}
              <input
                type="number"
                min={1}
                value={maxRedemptions}
                onChange={(event) => setMaxRedemptions(event.target.value)}
                placeholder={t("discountCodes.unlimited")}
              />
            </label>
          </div>
          <div className="row-actions">
            <label>
              {t("discountCodes.validFrom")}
              <input type="date" value={validFrom} onChange={(event) => setValidFrom(event.target.value)} />
            </label>
            <label>
              {t("discountCodes.validUntil")}
              <input type="date" value={validUntil} onChange={(event) => setValidUntil(event.target.value)} />
            </label>
          </div>
          <button type="submit" className="primary-button" disabled={busy}>
            {busy ? t("common.loading") : t("discountCodes.createButton")}
          </button>
        </form>
      </div>

      {loading ? <LoadingState /> : null}
      {!loading && codes.length === 0 ? <EmptyState message={t("discountCodes.empty")} icon="%" /> : null}

      {!loading && codes.length > 0 ? (
        <div className="list-stack">
          {codes.map((entry) => (
            <article key={entry.id} className="list-card">
              <div>
                <div className="list-card-title-row">
                  <strong>{entry.code}</strong>
                  <span
                    className={
                      entry.is_active ? "workflow-badge workflow-badge-published" : "workflow-badge workflow-badge-draft"
                    }
                  >
                    {entry.is_active ? t("discountCodes.active") : t("discountCodes.inactive")}
                  </span>
                </div>
                <p className="muted">
                  {describeValue(entry)}
                  {entry.min_order_cents > 0
                    ? ` · ${t("discountCodes.minOrderLabel", {
                        amount: formatMoney(entry.min_order_cents, "EUR", i18n.language),
                      })}`
                    : ""}
                  {" · "}
                  {t("discountCodes.redemptions", {
                    count: entry.redemption_count,
                    max: entry.max_redemptions ?? "∞",
                  })}
                  {entry.valid_until ? ` · ${t("discountCodes.untilLabel", { date: entry.valid_until.slice(0, 10) })}` : ""}
                </p>
              </div>
              <div className="list-card-actions">
                <button type="button" className="ghost-button" disabled={busy} onClick={() => void handleToggleActive(entry)}>
                  {entry.is_active ? t("discountCodes.deactivate") : t("discountCodes.activate")}
                </button>
                <button type="button" className="ghost-button danger" disabled={busy} onClick={() => void handleDelete(entry)}>
                  {t("discountCodes.delete")}
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}
