import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, Route, Routes, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";

import {
  checkoutShop,
  confirmShopOrder,
  fetchShopConfig,
  fetchShopMyCredits,
  fetchShopMyOrders,
  fetchShopMyReturns,
  fetchShopOrder,
  fetchShopProduct,
  fetchShopProducts,
  formatMoney,
  requestShopReturn,
  trackShopPageView,
  type ShopConfig,
  type ShopCreditLedgerEntry,
  type ShopOrder,
  type ShopProduct,
  type ShopReturn,
} from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { LanguageSwitch } from "../components/LanguageSwitch";
import { LoadingState } from "../components/LoadingState";
import { PwaInstallBanner } from "../components/PwaInstallBanner";
import { ShopHoneypot, ShopTurnstile } from "../components/ShopBotFields";
import {
  clearShopConsentDecision,
  loadShopConsent,
  saveShopConsent,
  ShopConsentBanner,
} from "../components/ShopConsentBanner";
import { ShopLogo } from "../components/ShopLogo";
import { ShopAuthProvider, useShopAuth } from "../hooks/useShopAuth";
import { ShopCartProvider, useShopCart } from "../hooks/useShopCart";

const SHOP_SESSION_KEY = "fuckco2-shop-session-v1";

function shopCompany(config: ShopConfig | null): string {
  return config?.company_name?.trim() || "carbonauten GmbH";
}

function shopBasePath(): string {
  const host = window.location.hostname.toLowerCase();
  if (host === "fuckco2.shop" || host === "www.fuckco2.shop") return "";
  if (new URLSearchParams(window.location.search).get("shop") === "1") return "";
  return "/shop";
}

function getOrCreateShopSessionId(): string {
  try {
    const existing = window.sessionStorage.getItem(SHOP_SESSION_KEY);
    if (existing && existing.length >= 8) return existing;
    const next =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `s-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    window.sessionStorage.setItem(SHOP_SESSION_KEY, next);
    return next;
  } catch {
    return `s-${Date.now()}`;
  }
}

function storefrontPath(pathname: string, base: string): string {
  if (!base) return pathname || "/";
  if (pathname === base) return "/";
  if (pathname.startsWith(`${base}/`)) {
    const rest = pathname.slice(base.length) || "/";
    return rest.startsWith("/") ? rest : `/${rest}`;
  }
  return pathname || "/";
}

function clampQty(value: number, max = 999) {
  if (!Number.isFinite(value)) return 1;
  return Math.min(max, Math.max(1, Math.floor(value)));
}

function ShopQtyStepper({
  value,
  onChange,
  disabled,
  max = 999,
}: {
  value: number;
  onChange: (next: number) => void;
  disabled?: boolean;
  max?: number;
}) {
  const { t } = useTranslation();
  return (
    <div className="shop-qty-stepper" role="group" aria-label={t("shop.quantity")}>
      <button
        type="button"
        className="shop-qty-btn"
        disabled={disabled || value <= 1}
        onClick={() => onChange(clampQty(value - 1, max))}
        aria-label="-"
      >
        −
      </button>
      <input
        type="number"
        min={1}
        max={max}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(clampQty(Number(event.target.value) || 1, max))}
      />
      <button
        type="button"
        className="shop-qty-btn"
        disabled={disabled || value >= max}
        onClick={() => onChange(clampQty(value + 1, max))}
        aria-label="+"
      >
        +
      </button>
    </div>
  );
}

function ShopProductCard({
  product,
  base,
  index = 0,
}: {
  product: ShopProduct;
  base: string;
  index?: number;
}) {
  const { t, i18n } = useTranslation();
  const cart = useShopCart();
  const [qty, setQty] = useState(1);
  const maxQty =
    product.track_inventory && product.stock_available != null
      ? Math.max(1, product.stock_available)
      : 999;
  const soldOut = product.in_stock === false;

  return (
    <article className="shop-card shop-card-static" style={{ animationDelay: `${Math.min(index, 8) * 60}ms` }}>
      <Link to={`${base}/p/${product.slug}`} className="shop-card-media">
        {product.image_url ? <img src={product.image_url} alt={product.name} /> : <div className="shop-card-placeholder" />}
      </Link>
      <div className="shop-card-body">
        <Link to={`${base}/p/${product.slug}`}>
          <h2>{product.name}</h2>
        </Link>
        <p className="shop-card-desc">{product.short_description || t("shop.noShortDescription")}</p>
        <div className="shop-card-price">
          <strong>{formatMoney(product.price_cents, product.currency, i18n.language)}</strong>
          <span>{t("shop.inclVat")}</span>
        </div>
        <div className="shop-card-actions">
          <ShopQtyStepper value={qty} onChange={setQty} disabled={soldOut} max={maxQty} />
          <button
            type="button"
            className="shop-btn shop-btn-primary"
            disabled={soldOut}
            onClick={() => {
              cart.addItem(product, qty);
              setQty(1);
            }}
          >
            {soldOut ? t("shop.soldOut") : t("shop.addToCart")}
          </button>
        </div>
      </div>
    </article>
  );
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
  const location = useLocation();
  const cart = useShopCart();
  const { customer, logout } = useShopAuth();
  const brand = config?.brand_name || "FuckCo2";
  const company = shopCompany(config);

  useEffect(() => {
    if (config && config.analytics_enabled === false) return;
    const consent = loadShopConsent();
    if (!consent?.analytics) return;
    const path = storefrontPath(location.pathname, base);
    void trackShopPageView({
      path,
      referrer: document.referrer || "",
      session_id: getOrCreateShopSessionId(),
      website: "",
    });
  }, [location.pathname, base, config]);

  return (
    <div className="shop-shell">
      <header className="shop-topbar">
        <Link to={base || "/"} className="shop-brand" aria-label={`${brand} — ${company}`}>
          <ShopLogo brand={brand} company={company} size="sm" showCompany />
        </Link>
        <div className="shop-topbar-actions">
          <LanguageSwitch />
          {customer ? (
            <>
              <Link to={`${base}/account`} className="shop-nav-link">
                {t("shop.account")}
                <span className="shop-credit-pill">{customer.co2_credit_balance} CO₂</span>
              </Link>
              <button type="button" className="shop-nav-link shop-nav-button" onClick={() => void logout()}>
                {t("auth.signOut")}
              </button>
            </>
          ) : (
            <>
              <Link to={`${base}/login`} className="shop-nav-link">
                {t("shop.login")}
              </Link>
              <Link to={`${base}/register`} className="shop-nav-link shop-nav-link-strong">
                {t("shop.register")}
              </Link>
            </>
          )}
          <Link to={`${base}/cart`} className="shop-cart-chip">
            {t("shop.cart")}
            <span>{cart.count}</span>
          </Link>
        </div>
      </header>
      <PwaInstallBanner variant="shop" />
      <main className="shop-main">{children}</main>
      <footer className="shop-footer">
        <div className="shop-footer-inner">
          <ShopLogo brand={brand} company={company} size="md" stacked showCompany />
          <p className="shop-footer-company">{t("shop.companyAttribution", { company })}</p>
          <nav className="shop-footer-links">
            <Link to={`${base}/legal/impressum`}>{t("shop.impressum")}</Link>
            <Link to={`${base}/legal/privacy`}>{t("shop.privacy")}</Link>
            <Link to={`${base}/legal/terms`}>{t("shop.terms")}</Link>
            <button
              type="button"
              className="shop-footer-consent"
              onClick={() => {
                clearShopConsentDecision();
              }}
            >
              {t("shop.cmp.settings")}
            </button>
            <a href={`mailto:${config?.contact_email || "hello@carbonauten.com"}`}>{t("shop.contact")}</a>
          </nav>
          <p>{t("shop.footerNote")}</p>
        </div>
      </footer>
      <ShopConsentBanner privacyHref={`${base}/legal/privacy`} />
    </div>
  );
}

function ShopHome({ config, base }: { config: ShopConfig | null; base: string }) {
  const { t } = useTranslation();
  const [products, setProducts] = useState<ShopProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const brand = config?.brand_name || "FuckCo2";
  const company = shopCompany(config);

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
      <section className="shop-hero-bleed">
        <div className="shop-hero-atmosphere" aria-hidden="true" />
        <div className="shop-hero-inner">
          <ShopLogo brand={brand} company={company} size="hero" stacked showCompany />
          <h1 className="shop-hero-title">{config?.tagline || t("shop.tagline")}</h1>
          <p className="shop-hero-copy">{t("shop.heroSubtitle")}</p>
          <p className="shop-hero-company">{t("shop.companyLine", { company })}</p>
          <div className="shop-hero-cta">
            <a href="#shop-catalog" className="shop-btn shop-btn-primary">
              {t("shop.browseProducts")}
            </a>
            <Link to={`${base}/register`} className="shop-btn shop-btn-ghost">
              {t("shop.registerCta")}
            </Link>
          </div>
        </div>
      </section>

      <section id="shop-catalog" className="shop-catalog">
        <header className="shop-section-head">
          <h2>{t("shop.catalogTitle")}</h2>
          <p>{t("shop.catalogSubtitle", { company })}</p>
        </header>
        {loading ? <LoadingState /> : null}
        {error ? <p className="error-text">{error}</p> : null}
        {!loading && products.length === 0 ? <EmptyState message={t("shop.empty")} icon="◈" /> : null}
        <div className="shop-grid">
          {products.map((product, index) => (
            <ShopProductCard key={product.id} product={product} base={base} index={index} />
          ))}
        </div>
      </section>
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
        <Link to={base || "/"} className="shop-btn shop-btn-ghost link-button">
          {t("shop.back")}
        </Link>
      </div>
    );
  }

  return (
    <article className="shop-detail">
      <Link to={base || "/"} className="shop-btn shop-btn-ghost link-button">
        {t("shop.back")}
      </Link>
      <div className="shop-detail-grid">
        <div className="shop-detail-media">
          {product.image_url ? <img src={product.image_url} alt={product.name} /> : <div className="shop-card-placeholder" />}
        </div>
        <div>
          <ShopLogo
            brand={config?.brand_name || "FuckCo2"}
            company={shopCompany(config)}
            size="sm"
            showCompany
          />
          <h1>{product.name}</h1>
          <p className="shop-price">{formatMoney(product.price_cents, product.currency, i18n.language)}</p>
          <p className="muted">{t("shop.inclVat")}</p>
          {product.short_description ? <p className="muted">{product.short_description}</p> : null}
          <div className="shop-description">{product.description || t("shop.noDescription")}</div>
          <div className="shop-qty-row">
            <div>
              <span className="muted">{t("shop.quantity")}</span>
              <ShopQtyStepper
                value={qty}
                onChange={setQty}
                disabled={product.in_stock === false}
                max={
                  product.track_inventory && product.stock_available != null
                    ? Math.max(1, product.stock_available)
                    : 999
                }
              />
            </div>
            <button
              type="button"
              className="shop-btn shop-btn-primary"
              disabled={product.in_stock === false}
              onClick={() => cart.addItem(product, qty)}
            >
              {product.in_stock === false ? t("shop.soldOut") : t("shop.addToCart")}
            </button>
          </div>
          <Link to={`${base}/cart`} className="shop-btn shop-btn-ghost link-button">
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
        <Link to={base || "/"} className="shop-btn shop-btn-primary link-button">
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
              <button type="button" className="shop-btn shop-btn-ghost" onClick={() => cart.removeItem(item.product_id)}>
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
        <Link to={`${base}/checkout`} className="shop-btn shop-btn-primary link-button">
          {t("shop.checkout")}
        </Link>
      </div>
    </section>
  );
}

function ShopCheckoutPage({ config, base }: { config: ShopConfig | null; base: string }) {
  const { t, i18n } = useTranslation();
  const cart = useShopCart();
  const { customer } = useShopAuth();
  const navigate = useNavigate();
  const [paymentMethod, setPaymentMethod] = useState<"stripe" | "invoice">(
    config?.stripe_enabled ? "stripe" : "invoice",
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [website, setWebsite] = useState("");
  const [turnstileToken, setTurnstileToken] = useState("");
  const onTurnstileToken = useCallback((token: string) => setTurnstileToken(token), []);
  const turnstileKey = config?.bot_protection?.turnstile_site_key || "";
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

  useEffect(() => {
    if (!customer) return;
    setForm((current) => ({
      ...current,
      email: customer.email,
      name: current.name || customer.name,
    }));
  }, [customer]);

  if (config?.require_account_checkout && !customer) {
    return (
      <section>
        <EmptyState message={t("shop.loginRequiredCheckout")} icon="☺" />
        <Link to={`${base}/login`} className="shop-btn shop-btn-primary link-button">
          {t("shop.login")}
        </Link>
      </section>
    );
  }

  if (cart.items.length === 0) {
    return (
      <div>
        <EmptyState message={t("shop.cartEmpty")} icon="◈" />
        <Link to={base || "/"} className="shop-btn shop-btn-primary link-button">
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
      if (config?.bot_protection?.turnstile_required && !turnstileToken) {
        setError(t("shop.captchaRequired"));
        setSaving(false);
        return;
      }
      const result = await checkoutShop({
        items: cart.items.map((item) => ({ product_id: item.product_id, quantity: item.quantity })),
        customer: form,
        payment_method: paymentMethod,
        notes: form.notes,
        website,
        turnstile_token: turnstileToken,
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

  const creditsPreview =
    customer && config?.co2_credits_per_euro
      ? Math.floor((cart.subtotalCents + (config.shipping_cents || 0)) / 100) * (config.co2_credits_per_euro || 0)
      : 0;

  return (
    <section className="shop-checkout">
      <h1>{t("shop.checkout")}</h1>
      {!customer ? (
        <p className="muted">
          {t("shop.creditsHintGuest")}{" "}
          <Link to={`${base}/register`}>{t("shop.register")}</Link>
        </p>
      ) : (
        <p className="muted">
          {t("shop.creditsHintMember", { credits: creditsPreview, balance: customer.co2_credit_balance })}
        </p>
      )}
      <form className="editor-form" onSubmit={(event) => void handleSubmit(event)}>
        <label>
          {t("shop.fieldEmail")}
          <input
            type="email"
            required
            value={form.email}
            disabled={Boolean(customer)}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
          />
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
        <ShopHoneypot value={website} onChange={setWebsite} />
        {turnstileKey ? <ShopTurnstile siteKey={turnstileKey} onToken={onTurnstileToken} /> : null}

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
        <button type="submit" className="shop-btn shop-btn-primary" disabled={saving}>
          {saving ? t("common.loading") : t("shop.placeOrder")}
        </button>
      </form>
    </section>
  );
}

function ShopAuthForm({
  mode,
  base,
  config,
}: {
  mode: "login" | "register";
  base: string;
  config: ShopConfig | null;
}) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { login, register, customer } = useShopAuth();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [privacyAccepted, setPrivacyAccepted] = useState(false);
  const [marketingOptIn, setMarketingOptIn] = useState(false);
  const [website, setWebsite] = useState("");
  const [turnstileToken, setTurnstileToken] = useState("");
  const onTurnstileToken = useCallback((token: string) => setTurnstileToken(token), []);
  const turnstileKey = config?.bot_protection?.turnstile_site_key || "";
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (customer) {
      navigate(`${base}/account`, { replace: true });
    }
  }, [customer, navigate, base]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      if (mode === "register" && !privacyAccepted) {
        setError(t("shop.privacyConsentRequired"));
        setSaving(false);
        return;
      }
      if (config?.bot_protection?.turnstile_required && !turnstileToken) {
        setError(t("shop.captchaRequired"));
        setSaving(false);
        return;
      }
      const extras = { website, turnstile_token: turnstileToken };
      if (mode === "login") {
        await login(email, password, extras);
      } else {
        await register({ email, name, password, language: i18n.language, ...extras });
        if (marketingOptIn) {
          saveShopConsent({ preferences: true, analytics: true, marketing: true });
        }
      }
      navigate(`${base}/account`);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="shop-auth-landing">
      <div className="shop-auth-hero">
        <ShopLogo
          brand={config?.brand_name || "FuckCo2"}
          company={shopCompany(config)}
          size="lg"
          stacked
          showCompany
        />
        <h1>{mode === "login" ? t("shop.authLandingLoginTitle") : t("shop.authLandingRegisterTitle")}</h1>
        <p className="muted">{t("shop.accountSubtitle")}</p>
        <p className="shop-hero-company">{t("shop.companyLine", { company: shopCompany(config) })}</p>
        <ul className="shop-auth-benefits">
          <li>{t("shop.authBenefit1")}</li>
          <li>{t("shop.authBenefit2")}</li>
          <li>{t("shop.authBenefit3")}</li>
        </ul>
      </div>
      <div className="shop-auth-card">
        <div className="shop-auth-tabs">
          <Link
            to={`${base}/login`}
            className={mode === "login" ? "shop-auth-tab active" : "shop-auth-tab"}
          >
            {t("shop.login")}
          </Link>
          <Link
            to={`${base}/register`}
            className={mode === "register" ? "shop-auth-tab active" : "shop-auth-tab"}
          >
            {t("shop.register")}
          </Link>
        </div>
        <form className="editor-form" onSubmit={(event) => void handleSubmit(event)}>
          {mode === "register" ? (
            <label>
              {t("shop.fieldName")}
              <input required value={name} onChange={(e) => setName(e.target.value)} />
            </label>
          ) : null}
          <label>
            {t("shop.fieldEmail")}
            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label>
            {t("auth.password")}
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          {mode === "register" ? (
            <>
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={privacyAccepted}
                  onChange={(e) => setPrivacyAccepted(e.target.checked)}
                  required
                />
                <span>
                  {t("shop.privacyConsentLabel")}{" "}
                  <Link to={`${base}/legal/privacy`}>{t("shop.privacy")}</Link>
                </span>
              </label>
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={marketingOptIn}
                  onChange={(e) => setMarketingOptIn(e.target.checked)}
                />
                <span>{t("shop.marketingConsentLabel")}</span>
              </label>
            </>
          ) : null}
          <ShopHoneypot value={website} onChange={setWebsite} />
          {turnstileKey ? <ShopTurnstile siteKey={turnstileKey} onToken={onTurnstileToken} /> : null}
          {error ? <p className="error-text">{error}</p> : null}
          <button type="submit" className="shop-btn shop-btn-primary" disabled={saving}>
            {saving ? t("common.loading") : mode === "login" ? t("shop.login") : t("shop.register")}
          </button>
        </form>
      </div>
    </section>
  );
}

function ShopAccountPage({ base }: { base: string }) {
  const { t, i18n } = useTranslation();
  const { customer, loading } = useShopAuth();
  const [orders, setOrders] = useState<ShopOrder[]>([]);
  const [returns, setReturns] = useState<ShopReturn[]>([]);
  const [ledger, setLedger] = useState<ShopCreditLedgerEntry[]>([]);
  const [balance, setBalance] = useState(0);
  const [reason, setReason] = useState("changed_mind");
  const [note, setNote] = useState("");
  const [activeOrderId, setActiveOrderId] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function reload() {
    if (!customer) return;
    const [nextOrders, nextReturns, credits] = await Promise.all([
      fetchShopMyOrders(),
      fetchShopMyReturns(),
      fetchShopMyCredits(),
    ]);
    setOrders(nextOrders);
    setReturns(nextReturns);
    setLedger(credits.ledger);
    setBalance(credits.balance);
  }

  useEffect(() => {
    if (!customer) return;
    void (async () => {
      try {
        await reload();
      } catch {
        /* ignore */
      }
    })();
  }, [customer]);

  async function submitReturn(orderId: string) {
    setSaving(true);
    setError("");
    setNotice("");
    try {
      await requestShopReturn(orderId, { reason, customer_note: note });
      setActiveOrderId("");
      setNote("");
      setNotice(t("shop.returnRequested"));
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <LoadingState />;
  if (!customer) {
    return (
      <section>
        <EmptyState message={t("shop.loginRequired")} icon="☺" />
        <Link to={`${base}/login`} className="shop-btn shop-btn-primary link-button">
          {t("shop.login")}
        </Link>
      </section>
    );
  }

  const openReturnOrderIds = new Set(
    returns.filter((item) => item.status === "requested" || item.status === "approved" || item.status === "completed").map((item) => item.order_id),
  );

  return (
    <section className="shop-success">
      <h1>{t("shop.account")}</h1>
      <p>
        {customer.name} · {customer.email}
      </p>
      <p>
        {t("shop.co2Balance")}: <strong>{balance}</strong>
      </p>
      {error ? <p className="error-text">{error}</p> : null}
      {notice ? <p className="success-text">{notice}</p> : null}
      <h2>{t("shop.myOrders")}</h2>
      {orders.length === 0 ? <p className="muted">{t("shop.noOrders")}</p> : null}
      <ul className="shop-account-orders">
        {orders.map((order) => {
          const canReturn =
            (order.status === "paid" || order.status === "fulfilled") && !openReturnOrderIds.has(order.id);
          return (
            <li key={order.id}>
              <div>
                {order.order_number} · {t(`shop.statusValues.${order.status}`, { defaultValue: order.status })} ·{" "}
                {formatMoney(order.total_cents, order.currency, i18n.language)}
                {order.credits_earned ? ` · +${order.credits_earned} CO₂` : ""}
              </div>
              {canReturn ? (
                activeOrderId === order.id ? (
                  <div className="shop-return-form">
                    <label>
                      {t("shop.returnReason")}
                      <select value={reason} onChange={(event) => setReason(event.target.value)}>
                        {["damaged", "wrong_item", "not_as_described", "changed_mind", "other"].map((item) => (
                          <option key={item} value={item}>
                            {t(`shopReturns.reasons.${item}`)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      {t("shop.returnNote")}
                      <textarea rows={2} value={note} onChange={(event) => setNote(event.target.value)} />
                    </label>
                    <div className="shop-return-actions">
                      <button
                        type="button"
                        className="shop-btn shop-btn-primary"
                        disabled={saving}
                        onClick={() => void submitReturn(order.id)}
                      >
                        {saving ? t("common.loading") : t("shop.submitReturn")}
                      </button>
                      <button type="button" className="shop-btn shop-btn-ghost" onClick={() => setActiveOrderId("")}>
                        {t("common.cancel")}
                      </button>
                    </div>
                  </div>
                ) : (
                  <button type="button" className="shop-btn shop-btn-ghost" onClick={() => setActiveOrderId(order.id)}>
                    {t("shop.requestReturn")}
                  </button>
                )
              ) : null}
            </li>
          );
        })}
      </ul>
      <h2>{t("shop.myReturns")}</h2>
      {returns.length === 0 ? <p className="muted">{t("shop.noReturns")}</p> : null}
      <ul>
        {returns.map((item) => (
          <li key={item.id}>
            {item.return_number} · {item.order_number} ·{" "}
            {t(`shopReturns.statusValues.${item.status}`, { defaultValue: item.status })} ·{" "}
            {t(`shopReturns.reasons.${item.reason}`, { defaultValue: item.reason })}
          </li>
        ))}
      </ul>
      <h2>{t("shop.creditHistory")}</h2>
      {ledger.length === 0 ? <p className="muted">{t("shop.noCreditsYet")}</p> : null}
      <ul>
        {ledger.map((entry) => (
          <li key={entry.id}>
            {entry.delta_credits > 0 ? "+" : ""}
            {entry.delta_credits} · {entry.reason}
            {entry.note ? ` — ${entry.note}` : ""}
          </li>
        ))}
      </ul>
      <Link to={base || "/"} className="shop-btn shop-btn-primary link-button">
        {t("shop.continueShopping")}
      </Link>
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
      {order.credits_earned ? (
        <p>
          {t("shop.creditsEarned", { credits: order.credits_earned })}
        </p>
      ) : null}
      <Link to={base || "/"} className="shop-btn shop-btn-primary link-button">
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
      <Link to={base || "/"} className="shop-btn shop-btn-ghost link-button">
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
      <Route path="/login" element={<ShopAuthForm mode="login" base={base} config={config} />} />
      <Route path="/register" element={<ShopAuthForm mode="register" base={base} config={config} />} />
      <Route path="/account" element={<ShopAccountPage base={base} />} />
      <Route path="/order/success" element={<ShopOrderSuccess base={base} />} />
      <Route path="/legal/impressum" element={<ShopLegalPage config={config} kind="impressum" base={base} />} />
      <Route path="/legal/privacy" element={<ShopLegalPage config={config} kind="privacy" base={base} />} />
      <Route path="/legal/terms" element={<ShopLegalPage config={config} kind="terms" base={base} />} />
      <Route path="/shop" element={<ShopHome config={config} base={base} />} />
      <Route path="/shop/p/:slug" element={<ShopProductDetail config={config} base={base} />} />
      <Route path="/shop/cart" element={<ShopCartPage config={config} base={base} />} />
      <Route path="/shop/checkout" element={<ShopCheckoutPage config={config} base={base} />} />
      <Route path="/shop/login" element={<ShopAuthForm mode="login" base={base} config={config} />} />
      <Route path="/shop/register" element={<ShopAuthForm mode="register" base={base} config={config} />} />
      <Route path="/shop/account" element={<ShopAccountPage base={base} />} />
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
    <ShopAuthProvider>
      <ShopCartProvider>
        <ShopShell config={config} base={base}>
          <ShopRoutes config={config} base={base} />
        </ShopShell>
      </ShopCartProvider>
    </ShopAuthProvider>
  );
}
