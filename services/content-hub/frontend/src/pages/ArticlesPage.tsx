import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { deleteArticle, fetchArticles, type Article } from "../api/client";
import { ArticleStatusBadge } from "../components/ArticleStatusBadge";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";
import { usePermissions } from "../hooks/usePermissions";

export function ArticlesPage() {
  const { t } = useTranslation();
  const { canEdit } = usePermissions();
  const [articles, setArticles] = useState<Article[]>([]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const items = await fetchArticles(query || undefined, status || undefined);
      setArticles(items);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [query, status]);

  async function handleDelete(id: string) {
    if (!window.confirm(t("articles.confirmDelete"))) return;
    await deleteArticle(id);
    await load();
  }

  return (
    <section className="page">
      <header className="page-header row-header">
        <div>
          <h1>{t("articles.title")}</h1>
          <p className="muted">{t("articles.subtitle")}</p>
        </div>
        {canEdit ? (
          <Link to="/articles/new" className="primary-button link-button">
            {t("articles.new")}
          </Link>
        ) : null}
      </header>

      <div className="toolbar">
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t("articles.searchPlaceholder")}
        />
        <select value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="">{t("articles.allStatuses")}</option>
          <option value="draft">{t("articles.statusDraft")}</option>
          <option value="review">{t("articles.statusReview")}</option>
          <option value="scheduled">{t("articles.statusScheduled")}</option>
          <option value="published">{t("articles.statusPublished")}</option>
          <option value="rejected">{t("articles.statusRejected")}</option>
        </select>
      </div>

      {loading ? <LoadingState /> : null}
      {error ? <p className="error-text">{error}</p> : null}

      {!loading && articles.length === 0 ? <EmptyState message={t("articles.empty")} icon="📝" /> : null}

      <div className="list-stack">
        {articles.map((article) => (
          <article key={article.id} className="list-card">
            <div>
              <div className="list-card-title-row">
                <h2>{article.title || t("articles.untitled")}</h2>
                <ArticleStatusBadge status={article.status} />
              </div>
              <p className="muted">{article.author_name}</p>
            </div>
            <div className="list-card-actions">
              <Link to={`/articles/${article.id}/edit`} className="ghost-button link-button">
                {t("articles.edit")}
              </Link>
              {canEdit ? (
                <button type="button" className="ghost-button danger" onClick={() => void handleDelete(article.id)}>
                  {t("articles.delete")}
                </button>
              ) : null}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
