import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, Route, Routes, useParams } from "react-router-dom";

import {
  fetchShopConfig,
  fetchShopProduct,
  fetchShopProducts,
  formatMoney,
  type ShopConfig,
  type ShopProduct,
} from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { LanguageSwitch } from "../components/LanguageSwitch";
import { LoadingState } from "../components/LoadingState";

function shopBasePath(): string {
  const host = window.location.hostname.toLowerCase();
  if (host === "fuckco2.shop" || host === "www.fuckco2.shop") {
    return "";
  }
  if (new URLSearchParams(window.location.search).get("shop") === "1") {
    return "";
  }
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
  return (
    <div className="shop-shell">
      <header className="shop-topbar">
        <Link to={base || "/"} className="shop-brand">
          <span className="shop-brand-mark">{config?.brand_name || "FuckCo2"}</span>
          <span className="shop-brand-tag">{config?.tagline || t("shop.tagline")}</span>
        </Link>
        <div className="shop-topbar-actions">
          <LanguageSwitch />
          <a className="ghost-button link-button" href={`mailto:${config?.contact_email || "hello@carbonauten.com"}`}>
            {t("shop.contact")}
          </a>
        </div>
      </header>
      <main className="shop-main">{children}</main>
      <footer className="shop-footer">
        <p>
          {config?.brand_name || "FuckCo2"} · {t("shop.footerNote")}
        </p>
      </footer>
    </div>
  );
}

function ShopHome({ config, base }: { config: ShopConfig | null; base: string }) {
  const { t, i18n } = useTranslation();
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
          <Link key={product.id} to={`${base}/p/${product.slug}`} className="shop-card">
            <div className="shop-card-media">
              {product.image_url ? (
                <img src={product.image_url} alt={product.name} />
              ) : (
                <div className="shop-card-placeholder" aria-hidden="true" />
              )}
            </div>
            <div className="shop-card-body">
              <h2>{product.name}</h2>
              <p className="muted">{product.short_description || t("shop.noShortDescription")}</p>
              <strong>{formatMoney(product.price_cents, product.currency, i18n.language)}</strong>
            </div>
          </Link>
        ))}
      </div>
    </>
  );
}

function ShopProductDetail({ config, base }: { config: ShopConfig | null; base: string }) {
  const { t, i18n } = useTranslation();
  const { slug = "" } = useParams();
  const [product, setProduct] = useState<ShopProduct | null>(null);
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

  const mailto = `mailto:${config?.contact_email || "hello@carbonauten.com"}?subject=${encodeURIComponent(
    t("shop.inquirySubject", { name: product.name }),
  )}`;

  return (
    <article className="shop-detail">
      <Link to={base || "/"} className="ghost-button link-button">
        {t("shop.back")}
      </Link>
      <div className="shop-detail-grid">
        <div className="shop-detail-media">
          {product.image_url ? (
            <img src={product.image_url} alt={product.name} />
          ) : (
            <div className="shop-card-placeholder" aria-hidden="true" />
          )}
        </div>
        <div>
          <p className="eyebrow">{config?.brand_name || "FuckCo2"}</p>
          <h1>{product.name}</h1>
          <p className="shop-price">{formatMoney(product.price_cents, product.currency, i18n.language)}</p>
          {product.short_description ? <p className="muted">{product.short_description}</p> : null}
          <div className="shop-description">{product.description || t("shop.noDescription")}</div>
          <a className="primary-button link-button" href={mailto}>
            {t("shop.requestProduct")}
          </a>
        </div>
      </div>
    </article>
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
    <ShopShell config={config} base={base}>
      <Routes>
        <Route path="/" element={<ShopHome config={config} base={base} />} />
        <Route path="/p/:slug" element={<ShopProductDetail config={config} base={base} />} />
        <Route path="/shop" element={<ShopHome config={config} base={base} />} />
        <Route path="/shop/p/:slug" element={<ShopProductDetail config={config} base={base} />} />
        <Route path="*" element={<ShopHome config={config} base={base} />} />
      </Routes>
    </ShopShell>
  );
}
