import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { deleteArticle, fetchArticles, type Article } from "../api/client";

export function ArticlesPage() {
  const { t } = useTranslation();
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
        <Link to="/articles/new" className="primary-button link-button">
          {t("articles.new")}
        </Link>
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
          <option value="published">{t("articles.statusPublished")}</option>
        </select>
      </div>

      {loading ? <p>{t("common.loading")}</p> : null}
      {error ? <p className="error-text">{error}</p> : null}

      {!loading && articles.length === 0 ? <div className="empty-state">{t("articles.empty")}</div> : null}

      <div className="list-stack">
        {articles.map((article) => (
          <article key={article.id} className="list-card">
            <div>
              <h2>{article.title || t("articles.untitled")}</h2>
              <p className="muted">
                {article.status === "published" ? t("articles.statusPublished") : t("articles.statusDraft")} · {article.author_name}
              </p>
            </div>
            <div className="list-card-actions">
              <Link to={`/articles/${article.id}/edit`} className="ghost-button link-button">
                {t("articles.edit")}
              </Link>
              <button type="button" className="ghost-button danger" onClick={() => void handleDelete(article.id)}>
                {t("articles.delete")}
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
