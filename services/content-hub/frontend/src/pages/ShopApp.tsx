import { FormEvent, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, Route, Routes, useNavigate, useParams, useSearchParams } from "react-router-dom";

import {
  checkoutShop,
  confirmShopOrder,
  fetchShopConfig,
  fetchShopOrder,
  fetchShopProduct,
  fetchShopProducts,
  formatMoney,
  type ShopConfig,
  type ShopOrder,
  type ShopProduct,
} from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { LanguageSwitch } from "../components/LanguageSwitch";
import { LoadingState } from "../components/LoadingState";
import { ShopCartProvider, useShopCart } from "../hooks/useShopCart";

function shopBasePath(): string {
  const host = window.location.hostname.toLowerCase();
  if (host === "fuckco2.shop" || host === "www.fuckco2.shop") return "";
  if (new URLSearchParams(window.location.search).get("shop") === "1") return "";
  return "/shop";
}

function ShopShell({
  children,
  config,
  base,
}: {
  children: React.ReactNode;
  config: ShopConfig | null;
  base: string;
}) {
  const { t } = useTranslation();
  const cart = useShopCart();
  return (
    <div className="shop-shell">
      <header className="shop-topbar">
        <Link to={base || "/"} className="shop-brand">
          <span className="shop-brand-mark">{config?.brand_name || "FuckCo2"}</span>
          <span className="shop-brand-tag">{config?.tagline || t("shop.tagline")}</span>
        </Link>
        <div className="shop-topbar-actions">
          <LanguageSwitch />
          <Link to={`${base}/cart`} className="primary-button link-button">
            {t("shop.cart")} ({cart.count})
          </Link>
        </div>
      </header>
      <main className="shop-main">{children}</main>
      <footer className="shop-footer">
        <nav className="shop-footer-links">
          <Link to={`${base}/legal/impressum`}>{t("shop.impressum")}</Link>
          <Link to={`${base}/legal/privacy`}>{t("shop.privacy")}</Link>
          <Link to={`${base}/legal/terms`}>{t("shop.terms")}</Link>
          <a href={`mailto:${config?.contact_email || "hello@carbonauten.com"}`}>{t("shop.contact")}</a>
        </nav>
        <p>
          {config?.brand_name || "FuckCo2"} · {t("shop.footerNote")}
        </p>
      </footer>
    </div>
  );
}

function ShopHome({ config, base }: { config: ShopConfig | null; base: string }) {
  const { t, i18n } = useTranslation();
  const cart = useShopCart();
  const [products, setProducts] = useState<ShopProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    void (async () => {
      try {
        setProducts(await fetchShopProducts());
      } catch (err) {
        setError(err instanceof Error ? err.message : t("common.error"));
      } finally {
        setLoading(false);
      }
    })();
  }, [t]);

  return (
    <>
      <section className="shop-hero">
        <p className="eyebrow">{config?.brand_name || "FuckCo2"}</p>
        <h1>{t("shop.heroTitle")}</h1>
        <p className="muted">{t("shop.heroSubtitle")}</p>
      </section>
      {loading ? <LoadingState /> : null}
      {error ? <p className="error-text">{error}</p> : null}
      {!loading && products.length === 0 ? <EmptyState message={t("shop.empty")} icon="◈" /> : null}
      <div className="shop-grid">
        {products.map((product) => (
          <article key={product.id} className="shop-card shop-card-static">
            <Link to={`${base}/p/${product.slug}`} className="shop-card-media">
              {product.image_url ? <img src={product.image_url} alt={product.name} /> : <div className="shop-card-placeholder" />}
            </Link>
            <div className="shop-card-body">
              <Link to={`${base}/p/${product.slug}`}>
                <h2>{product.name}</h2>
              </Link>
              <p className="muted">{product.short_description || t("shop.noShortDescription")}</p>
              <strong>{formatMoney(product.price_cents, product.currency, i18n.language)}</strong>
              <p className="muted shop-vat-note">{t("shop.inclVat")}</p>
              <button
                type="button"
                className="primary-button"
                disabled={product.in_stock === false}
                onClick={() => cart.addItem(product)}
              >
                {product.in_stock === false ? t("shop.soldOut") : t("shop.addToCart")}
              </button>
            </div>
          </article>
        ))}
      </div>
    </>
  );
}

function ShopProductDetail({ config, base }: { config: ShopConfig | null; base: string }) {
  const { t, i18n } = useTranslation();
  const { slug = "" } = useParams();
  const cart = useShopCart();
  const [product, setProduct] = useState<ShopProduct | null>(null);
  const [qty, setQty] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    void (async () => {
      setLoading(true);
      try {
        setProduct(await fetchShopProduct(slug));
      } catch (err) {
        setError(err instanceof Error ? err.message : t("common.error"));
      } finally {
        setLoading(false);
      }
    })();
  }, [slug, t]);

  if (loading) return <LoadingState />;
  if (error || !product) {
    return (
      <div>
        <p className="error-text">{error || t("shop.notFound")}</p>
        <Link to={base || "/"} className="ghost-button link-button">
          {t("shop.back")}
        </Link>
      </div>
    );
  }

  return (
    <article className="shop-detail">
      <Link to={base || "/"} className="ghost-button link-button">
        {t("shop.back")}
      </Link>
      <div className="shop-detail-grid">
        <div className="shop-detail-media">
          {product.image_url ? <img src={product.image_url} alt={product.name} /> : <div className="shop-card-placeholder" />}
        </div>
        <div>
          <p className="eyebrow">{config?.brand_name || "FuckCo2"}</p>
          <h1>{product.name}</h1>
          <p className="shop-price">{formatMoney(product.price_cents, product.currency, i18n.language)}</p>
          <p className="muted">{t("shop.inclVat")}</p>
          {product.short_description ? <p className="muted">{product.short_description}</p> : null}
          <div className="shop-description">{product.description || t("shop.noDescription")}</div>
          <div className="shop-qty-row">
            <label>
              {t("shop.quantity")}
              <input
                type="number"
                min={1}
                max={999}
                value={qty}
                onChange={(event) => setQty(Math.max(1, Number(event.target.value) || 1))}
              />
            </label>
            <button
              type="button"
              className="primary-button"
              disabled={product.in_stock === false}
              onClick={() => cart.addItem(product, qty)}
            >
              {product.in_stock === false ? t("shop.soldOut") : t("shop.addToCart")}
            </button>
          </div>
          <Link to={`${base}/cart`} className="ghost-button link-button">
            {t("shop.gotoCart")}
          </Link>
        </div>
      </div>
    </article>
  );
}

function ShopCartPage({ config, base }: { config: ShopConfig | null; base: string }) {
  const { t, i18n } = useTranslation();
  const cart = useShopCart();
  const shipping = useMemo(() => {
    const fee = config?.shipping_cents || 0;
    const freeFrom = config?.free_shipping_from_cents || 0;
    if (freeFrom > 0 && cart.subtotalCents >= freeFrom) return 0;
    return fee;
  }, [config, cart.subtotalCents]);

  if (cart.items.length === 0) {
    return (
      <div>
        <h1>{t("shop.cart")}</h1>
        <EmptyState message={t("shop.cartEmpty")} icon="◈" />
        <Link to={base || "/"} className="primary-button link-button">
          {t("shop.continueShopping")}
        </Link>
      </div>
    );
  }

  return (
    <section className="shop-cart">
      <h1>{t("shop.cart")}</h1>
      <div className="list-stack">
        {cart.items.map((item) => (
          <article key={item.product_id} className="list-card shop-cart-line">
            <div>
              <strong>{item.name}</strong>
              <p className="muted">{formatMoney(item.price_cents, item.currency, i18n.language)}</p>
            </div>
            <div className="shop-cart-controls">
              <input
                type="number"
                min={1}
                value={item.quantity}
                onChange={(event) => cart.setQuantity(item.product_id, Math.max(1, Number(event.target.value) || 1))}
              />
              <button type="button" className="ghost-button" onClick={() => cart.removeItem(item.product_id)}>
                {t("shop.remove")}
              </button>
            </div>
            <strong>{formatMoney(item.price_cents * item.quantity, item.currency, i18n.language)}</strong>
          </article>
        ))}
      </div>
      <div className="shop-cart-summary">
        <p>
          {t("shop.subtotal")}: <strong>{formatMoney(cart.subtotalCents, config?.currency || "EUR", i18n.language)}</strong>
        </p>
        <p>
          {t("shop.shipping")}: <strong>{formatMoney(shipping, config?.currency || "EUR", i18n.language)}</strong>
        </p>
        <p>
          {t("shop.total")}:{" "}
          <strong>{formatMoney(cart.subtotalCents + shipping, config?.currency || "EUR", i18n.language)}</strong>
        </p>
        <Link to={`${base}/checkout`} className="primary-button link-button">
          {t("shop.checkout")}
        </Link>
      </div>
    </section>
  );
}

function ShopCheckoutPage({ config, base }: { config: ShopConfig | null; base: string }) {
  const { t, i18n } = useTranslation();
  const cart = useShopCart();
  const navigate = useNavigate();
  const [paymentMethod, setPaymentMethod] = useState<"stripe" | "invoice">(
    config?.stripe_enabled ? "stripe" : "invoice",
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    email: "",
    name: "",
    phone: "",
    company: "",
    address_line1: "",
    address_line2: "",
    postal_code: "",
    city: "",
    country: "DE",
    notes: "",
  });

  useEffect(() => {
    if (config?.stripe_enabled) setPaymentMethod("stripe");
    else setPaymentMethod("invoice");
  }, [config?.stripe_enabled]);

  if (cart.items.length === 0) {
    return (
      <div>
        <EmptyState message={t("shop.cartEmpty")} icon="◈" />
        <Link to={base || "/"} className="primary-button link-button">
          {t("shop.continueShopping")}
        </Link>
      </div>
    );
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const result = await checkoutShop({
        items: cart.items.map((item) => ({ product_id: item.product_id, quantity: item.quantity })),
        customer: form,
        payment_method: paymentMethod,
        notes: form.notes,
      });
      cart.clear();
      if (result.checkout_url) {
        window.location.href = result.checkout_url;
        return;
      }
      navigate(
        `${base}/order/success?order=${encodeURIComponent(result.order.order_number)}&token=${encodeURIComponent(result.order.access_token || "")}`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="shop-checkout">
      <h1>{t("shop.checkout")}</h1>
      <form className="editor-form" onSubmit={(event) => void handleSubmit(event)}>
        <label>
          {t("shop.fieldEmail")}
          <input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        </label>
        <label>
          {t("shop.fieldName")}
          <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </label>
        <div className="form-grid">
          <label>
            {t("shop.fieldPhone")}
            <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          </label>
          <label>
            {t("shop.fieldCompany")}
            <input value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} />
          </label>
        </div>
        <label>
          {t("shop.fieldAddress")}
          <input required value={form.address_line1} onChange={(e) => setForm({ ...form, address_line1: e.target.value })} />
        </label>
        <label>
          {t("shop.fieldAddress2")}
          <input value={form.address_line2} onChange={(e) => setForm({ ...form, address_line2: e.target.value })} />
        </label>
        <div className="form-grid">
          <label>
            {t("shop.fieldPostal")}
            <input required value={form.postal_code} onChange={(e) => setForm({ ...form, postal_code: e.target.value })} />
          </label>
          <label>
            {t("shop.fieldCity")}
            <input required value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} />
          </label>
        </div>
        <label>
          {t("shop.fieldCountry")}
          <input required maxLength={2} value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value.toUpperCase() })} />
        </label>
        <label>
          {t("shop.fieldNotes")}
          <textarea rows={3} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
        </label>

        <fieldset className="shop-payment-methods">
          <legend>{t("shop.paymentMethod")}</legend>
          {config?.stripe_enabled ? (
            <label className="checkbox-row">
              <input type="radio" checked={paymentMethod === "stripe"} onChange={() => setPaymentMethod("stripe")} />
              {t("shop.payCard")}
            </label>
          ) : null}
          <label className="checkbox-row">
            <input type="radio" checked={paymentMethod === "invoice"} onChange={() => setPaymentMethod("invoice")} />
            {t("shop.payInvoice")}
          </label>
        </fieldset>

        <p className="muted">
          {t("shop.orderSummary")}: {formatMoney(cart.subtotalCents, config?.currency || "EUR", i18n.language)} · {cart.count}{" "}
          {t("shop.items")}
        </p>
        {error ? <p className="error-text">{error}</p> : null}
        <button type="submit" className="primary-button" disabled={saving}>
          {saving ? t("common.loading") : t("shop.placeOrder")}
        </button>
      </form>
    </section>
  );
}

function ShopOrderSuccess({ base }: { base: string }) {
  const { t, i18n } = useTranslation();
  const [params] = useSearchParams();
  const [order, setOrder] = useState<ShopOrder | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      const orderNumber = params.get("order") || "";
      const token = params.get("token") || "";
      const sessionId = params.get("session_id") || "";
      if (!orderNumber || !token) {
        setError(t("shop.notFound"));
        setLoading(false);
        return;
      }
      try {
        if (sessionId) {
          setOrder(await confirmShopOrder(orderNumber, token, sessionId));
        } else {
          setOrder(await fetchShopOrder(orderNumber, token));
        }
      } catch (err) {
        try {
          setOrder(await fetchShopOrder(orderNumber, token));
        } catch {
          setError(err instanceof Error ? err.message : t("common.error"));
        }
      } finally {
        setLoading(false);
      }
    })();
  }, [params, t]);

  if (loading) return <LoadingState />;
  if (error || !order) return <p className="error-text">{error || t("shop.notFound")}</p>;

  return (
    <section className="shop-success">
      <h1>{t("shop.thankYou")}</h1>
      <p>
        {t("shop.orderNumber")}: <strong>{order.order_number}</strong>
      </p>
      <p>
        {t("shop.status")}: <strong>{t(`shop.statusValues.${order.status}`, { defaultValue: order.status })}</strong>
      </p>
      <p>
        {t("shop.total")}: <strong>{formatMoney(order.total_cents, order.currency, i18n.language)}</strong>
      </p>
      {order.payment_method === "invoice" ? <p className="muted">{t("shop.invoiceHint")}</p> : null}
      <Link to={base || "/"} className="primary-button link-button">
        {t("shop.continueShopping")}
      </Link>
    </section>
  );
}

function ShopLegalPage({
  config,
  kind,
  base,
}: {
  config: ShopConfig | null;
  kind: "impressum" | "privacy" | "terms";
  base: string;
}) {
  const { t } = useTranslation();
  const content =
    kind === "impressum"
      ? config?.legal?.impressum
      : kind === "privacy"
        ? config?.legal?.privacy
        : config?.legal?.terms;
  const title = t(`shop.${kind}`);
  return (
    <section className="shop-legal">
      <Link to={base || "/"} className="ghost-button link-button">
        {t("shop.back")}
      </Link>
      <h1>{title}</h1>
      <pre className="shop-legal-body">{content?.trim() || t("shop.legalPlaceholder")}</pre>
    </section>
  );
}

function ShopRoutes({ config, base }: { config: ShopConfig | null; base: string }) {
  return (
    <Routes>
      <Route path="/" element={<ShopHome config={config} base={base} />} />
      <Route path="/p/:slug" element={<ShopProductDetail config={config} base={base} />} />
      <Route path="/cart" element={<ShopCartPage config={config} base={base} />} />
      <Route path="/checkout" element={<ShopCheckoutPage config={config} base={base} />} />
      <Route path="/order/success" element={<ShopOrderSuccess base={base} />} />
      <Route path="/legal/impressum" element={<ShopLegalPage config={config} kind="impressum" base={base} />} />
      <Route path="/legal/privacy" element={<ShopLegalPage config={config} kind="privacy" base={base} />} />
      <Route path="/legal/terms" element={<ShopLegalPage config={config} kind="terms" base={base} />} />
      <Route path="/shop" element={<ShopHome config={config} base={base} />} />
      <Route path="/shop/p/:slug" element={<ShopProductDetail config={config} base={base} />} />
      <Route path="/shop/cart" element={<ShopCartPage config={config} base={base} />} />
      <Route path="/shop/checkout" element={<ShopCheckoutPage config={config} base={base} />} />
      <Route path="/shop/order/success" element={<ShopOrderSuccess base={base} />} />
      <Route path="/shop/legal/impressum" element={<ShopLegalPage config={config} kind="impressum" base={base} />} />
      <Route path="/shop/legal/privacy" element={<ShopLegalPage config={config} kind="privacy" base={base} />} />
      <Route path="/shop/legal/terms" element={<ShopLegalPage config={config} kind="terms" base={base} />} />
      <Route path="*" element={<ShopHome config={config} base={base} />} />
    </Routes>
  );
}

export function ShopApp() {
  const [config, setConfig] = useState<ShopConfig | null>(null);
  const base = shopBasePath();

  useEffect(() => {
    void (async () => {
      try {
        setConfig(await fetchShopConfig());
      } catch {
        setConfig(null);
      }
    })();
  }, []);

  return (
    <ShopCartProvider>
      <ShopShell config={config} base={base}>
        <ShopRoutes config={config} base={base} />
      </ShopShell>
    </ShopCartProvider>
  );
}
