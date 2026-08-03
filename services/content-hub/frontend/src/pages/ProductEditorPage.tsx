import { FormEvent, useEffect, useState, type ChangeEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  createProduct,
  fetchProduct,
  formatMoney,
  updateProduct,
  uploadFile,
} from "../api/client";
import { LoadingState } from "../components/LoadingState";

export function ProductEditorPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { id } = useParams();
  const isNew = !id || id === "new";

  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [shortDescription, setShortDescription] = useState("");
  const [description, setDescription] = useState("");
  const [priceEuros, setPriceEuros] = useState("0.00");
  const [currency, setCurrency] = useState("EUR");
  const [sku, setSku] = useState("");
  const [isPublished, setIsPublished] = useState(false);
  const [sortOrder, setSortOrder] = useState(0);
  const [trackInventory, setTrackInventory] = useState(false);
  const [stockQty, setStockQty] = useState(0);
  const [vatRate, setVatRate] = useState("19");
  const [imageFileAssetId, setImageFileAssetId] = useState<string | null>(null);
  const [imageName, setImageName] = useState<string | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (isNew || !id) return;
    void (async () => {
      try {
        const product = await fetchProduct(id);
        setName(product.name);
        setSlug(product.slug);
        setShortDescription(product.short_description);
        setDescription(product.description);
        setPriceEuros((product.price_cents / 100).toFixed(2));
        setCurrency(product.currency || "EUR");
        setSku(product.sku);
        setIsPublished(product.is_published);
        setSortOrder(product.sort_order);
        setTrackInventory(Boolean(product.track_inventory));
        setStockQty(product.stock_qty || 0);
        setVatRate(String(((product.vat_rate_bps || 1900) / 100).toFixed(0)));
        setImageFileAssetId(product.image_file_asset_id);
        setImageName(product.image_name || null);
        setImageUrl(product.image_url || null);
      } catch (err) {
        setError(err instanceof Error ? err.message : t("common.error"));
      } finally {
        setLoading(false);
      }
    })();
  }, [id, isNew, t]);

  async function handleImageChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setSaving(true);
    setError("");
    try {
      const uploaded = await uploadFile(file, "products");
      setImageFileAssetId(uploaded.id);
      setImageName(uploaded.original_name);
      setImageUrl(null);
      setNotice(t("products.imageUploaded"));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setSaving(false);
      event.target.value = "";
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setNotice("");
    const price_cents = Math.round(Number.parseFloat(priceEuros.replace(",", ".")) * 100);
    if (!Number.isFinite(price_cents) || price_cents < 0) {
      setError(t("products.invalidPrice"));
      setSaving(false);
      return;
    }
    const payload = {
      name,
      slug: slug || undefined,
      short_description: shortDescription,
      description,
      price_cents,
      currency,
      sku,
      is_published: isPublished,
      sort_order: sortOrder,
      image_file_asset_id: imageFileAssetId,
      track_inventory: trackInventory,
      stock_qty: stockQty,
      vat_rate_bps: Math.round(Number.parseFloat(vatRate.replace(",", ".")) * 100) || 1900,
    };
    try {
      if (isNew) {
        const product = await createProduct(payload);
        navigate(`/products/${product.id}/edit`, { replace: true });
        setNotice(t("products.saved"));
        return;
      }
      const updated = await updateProduct(id!, payload);
      setSlug(updated.slug);
      setImageUrl(updated.image_url || null);
      setNotice(t("products.saved"));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <LoadingState />;
  }

  const previewCents = Math.round(Number.parseFloat(priceEuros.replace(",", ".") || "0") * 100) || 0;

  return (
    <section className="page">
      <header className="page-header row-header">
        <div>
          <h1>{isNew ? t("products.new") : t("products.edit")}</h1>
          <p className="muted">{t("products.editorSubtitle")}</p>
        </div>
        <Link to="/products" className="ghost-button link-button">
          {t("products.back")}
        </Link>
      </header>

      <form className="editor-form" onSubmit={(event) => void handleSubmit(event)}>
        <label>
          {t("products.fieldName")}
          <input value={name} onChange={(event) => setName(event.target.value)} required />
        </label>

        <label>
          {t("products.fieldSlug")}
          <input
            value={slug}
            onChange={(event) => setSlug(event.target.value)}
            placeholder={t("products.slugHint")}
          />
        </label>

        <label>
          {t("products.fieldShortDescription")}
          <input
            value={shortDescription}
            onChange={(event) => setShortDescription(event.target.value)}
            maxLength={500}
          />
        </label>

        <label>
          {t("products.fieldDescription")}
          <textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={8} />
        </label>

        <div className="form-grid">
          <label>
            {t("products.fieldPrice")}
            <input
              value={priceEuros}
              onChange={(event) => setPriceEuros(event.target.value)}
              inputMode="decimal"
              required
            />
          </label>
          <label>
            {t("products.fieldCurrency")}
            <select value={currency} onChange={(event) => setCurrency(event.target.value)}>
              <option value="EUR">EUR</option>
              <option value="USD">USD</option>
              <option value="CNY">CNY</option>
            </select>
          </label>
        </div>
        <p className="muted">{formatMoney(previewCents, currency, i18n.language)}</p>

        <div className="form-grid">
          <label>
            {t("products.fieldSku")}
            <input value={sku} onChange={(event) => setSku(event.target.value)} />
          </label>
          <label>
            {t("products.fieldSortOrder")}
            <input
              type="number"
              value={sortOrder}
              onChange={(event) => setSortOrder(Number(event.target.value) || 0)}
            />
          </label>
        </div>

        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={isPublished}
            onChange={(event) => setIsPublished(event.target.checked)}
          />
          {t("products.fieldPublished")}
        </label>

        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={trackInventory}
            onChange={(event) => setTrackInventory(event.target.checked)}
          />
          {t("products.fieldTrackInventory")}
        </label>

        <div className="form-grid">
          <label>
            {t("products.fieldStock")}
            <input
              type="number"
              min={0}
              value={stockQty}
              onChange={(event) => setStockQty(Number(event.target.value) || 0)}
              disabled={!trackInventory}
            />
          </label>
          <label>
            {t("products.fieldVat")}
            <input value={vatRate} onChange={(event) => setVatRate(event.target.value)} />
          </label>
        </div>

        <label>
          {t("products.fieldImage")}
          <input type="file" accept="image/*" onChange={(event) => void handleImageChange(event)} />
        </label>
        {imageName ? <p className="muted">{t("products.attachedImage")}: {imageName}</p> : null}
        {imageUrl ? (
          <img src={imageUrl} alt="" className="product-image-preview" />
        ) : null}

        {notice ? <p className="success-text" role="status">{notice}</p> : null}
        {error ? <p className="error-text">{error}</p> : null}

        <div className="header-actions">
          <button type="submit" className="primary-button" disabled={saving}>
            {saving ? t("common.loading") : t("products.save")}
          </button>
        </div>
      </form>
    </section>
  );
}
