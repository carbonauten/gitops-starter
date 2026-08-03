import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { deleteProduct, fetchProducts, formatMoney, type Product } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";
import { usePermissions } from "../hooks/usePermissions";

export function ProductsPage() {
  const { t, i18n } = useTranslation();
  const { canEdit } = usePermissions();
  const [products, setProducts] = useState<Product[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      setProducts(await fetchProducts(query || undefined));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [query]);

  async function handleDelete(id: string) {
    if (!window.confirm(t("products.confirmDelete"))) return;
    await deleteProduct(id);
    await load();
  }

  return (
    <section className="page">
      <header className="page-header row-header">
        <div>
          <h1>{t("products.title")}</h1>
          <p className="muted">{t("products.subtitle")}</p>
        </div>
        <div className="header-actions">
          <a href="https://fuckco2.shop" className="ghost-button link-button" target="_blank" rel="noreferrer">
            {t("products.openShop")}
          </a>
          {canEdit ? (
            <Link to="/products/new" className="primary-button link-button">
              {t("products.new")}
            </Link>
          ) : null}
        </div>
      </header>

      <div className="toolbar">
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t("products.searchPlaceholder")}
        />
      </div>

      {loading ? <LoadingState /> : null}
      {error ? <p className="error-text">{error}</p> : null}
      {!loading && products.length === 0 ? <EmptyState message={t("products.empty")} icon="◈" /> : null}

      {!loading && products.length > 0 ? (
        <div className="list-stack">
          {products.map((product) => (
            <article key={product.id} className="list-card">
              <div className="list-card-title-row">
                <Link to={`/products/${product.id}/edit`}>
                  <strong>{product.name}</strong>
                </Link>
                <span className={product.is_published ? "workflow-badge workflow-badge-published" : "workflow-badge workflow-badge-draft"}>
                  {product.is_published ? t("products.published") : t("products.draft")}
                </span>
              </div>
              <p className="muted">
                {formatMoney(product.price_cents, product.currency, i18n.language)}
                {product.sku ? ` · SKU ${product.sku}` : ""}
                {product.short_description ? ` · ${product.short_description}` : ""}
              </p>
              {canEdit ? (
                <div className="list-card-actions">
                  <Link to={`/products/${product.id}/edit`} className="ghost-button link-button">
                    {t("products.edit")}
                  </Link>
                  <button type="button" className="ghost-button" onClick={() => void handleDelete(product.id)}>
                    {t("products.delete")}
                  </button>
                </div>
              ) : null}
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}
