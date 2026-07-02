import { FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import {
  createArticle,
  fetchArticle,
  fetchArticleTemplates,
  updateArticle,
  type ArticleTemplate,
} from "../api/client";
import { ArticleEditor } from "../components/ArticleEditor";

export function ArticleEditorPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const isNew = !id || id === "new";

  const [title, setTitle] = useState("");
  const [content, setContent] = useState("<p></p>");
  const [status, setStatus] = useState<"draft" | "published">("draft");
  const [templates, setTemplates] = useState<ArticleTemplate[]>([]);
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    void (async () => {
      const items = await fetchArticleTemplates();
      setTemplates(items);

      const templateId = searchParams.get("template");
      if (isNew && templateId) {
        const template = items.find((item) => item.id === templateId);
        if (template) {
          setTitle(template.title);
          setContent(template.content);
        }
      }

      if (!isNew && id) {
        try {
          const article = await fetchArticle(id);
          setTitle(article.title);
          setContent(article.content || "<p></p>");
          setStatus(article.status);
        } catch (err) {
          setError(err instanceof Error ? err.message : t("common.error"));
        } finally {
          setLoading(false);
        }
      }
    })();
  }, [id, isNew, searchParams, t]);

  async function handleSubmit(event: FormEvent, nextStatus: "draft" | "published") {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      if (isNew) {
        const article = await createArticle({ title, content, status: nextStatus });
        navigate(`/articles/${article.id}/edit`, { replace: true });
        return;
      }
      await updateArticle(id!, { title, content, status: nextStatus });
      setStatus(nextStatus);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <p>{t("common.loading")}</p>;
  }

  return (
    <section className="page">
      <header className="page-header row-header">
        <div>
          <h1>{isNew ? t("articles.new") : t("articles.edit")}</h1>
          <p className="muted">{t("articles.editorSubtitle")}</p>
        </div>
        <Link to="/articles" className="ghost-button link-button">
          {t("articles.back")}
        </Link>
      </header>

      {isNew && templates.length > 0 ? (
        <div className="template-row">
          <span className="muted">{t("articles.templates")}</span>
          {templates.map((template) => (
            <Link key={template.id} to={`/articles/new?template=${template.id}`} className="badge link-badge">
              {template.title}
            </Link>
          ))}
        </div>
      ) : null}

      <form className="editor-form" onSubmit={(event) => void handleSubmit(event, status)}>
        <label>
          {t("articles.fieldTitle")}
          <input value={title} onChange={(event) => setTitle(event.target.value)} required />
        </label>

        <label>
          {t("articles.fieldContent")}
          <ArticleEditor content={content} onChange={setContent} />
        </label>

        {error ? <p className="error-text">{error}</p> : null}

        <div className="form-actions">
          <button type="button" className="ghost-button" disabled={saving} onClick={(event) => void handleSubmit(event, "draft")}>
            {t("articles.saveDraft")}
          </button>
          <button type="button" className="primary-button" disabled={saving} onClick={(event) => void handleSubmit(event, "published")}>
            {t("articles.publish")}
          </button>
        </div>
      </form>
    </section>
  );
}
