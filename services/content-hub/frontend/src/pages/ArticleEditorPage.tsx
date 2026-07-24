import { FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import {
  createArticle,
  fetchArticle,
  fetchArticleTemplates,
  submitArticleForReview,
  updateArticle,
  type ArticleTemplate,
} from "../api/client";
import { ArticleEditor } from "../components/ArticleEditor";
import { AiAssistPanel } from "../components/AiAssistPanel";
import { VersionHistoryPanel } from "../components/VersionHistoryPanel";
import { LoadingState } from "../components/LoadingState";

const EDITABLE_STATUSES = new Set(["draft", "rejected"]);

export function ArticleEditorPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const isNew = !id || id === "new";

  const [title, setTitle] = useState("");
  const [content, setContent] = useState("<p></p>");
  const [status, setStatus] = useState<"draft" | "review" | "rejected" | "scheduled" | "published">("draft");
  const [reviewComment, setReviewComment] = useState("");
  const [scheduledAt, setScheduledAt] = useState<string | null>(null);
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
          setReviewComment(article.review_comment || "");
          setScheduledAt(article.scheduled_publish_at || null);
        } catch (err) {
          setError(err instanceof Error ? err.message : t("common.error"));
        } finally {
          setLoading(false);
        }
      }
    })();
  }, [id, isNew, searchParams, t]);

  const canEditContent = isNew || EDITABLE_STATUSES.has(status);

  async function handleSaveDraft(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      if (isNew) {
        const article = await createArticle({ title, content });
        navigate(`/articles/${article.id}/edit`, { replace: true });
        return;
      }
      await updateArticle(id!, { title, content });
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setSaving(false);
    }
  }

  async function handleSubmitReview(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      let articleId = id;
      if (isNew) {
        const article = await createArticle({ title, content });
        articleId = article.id;
        navigate(`/articles/${article.id}/edit`, { replace: true });
      } else {
        await updateArticle(id!, { title, content });
      }
      if (articleId) {
        const article = await submitArticleForReview(articleId);
        setStatus(article.status);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setSaving(false);
    }
  }

  function statusLabel(value: typeof status): string {
    switch (value) {
      case "review":
        return t("articles.statusReview");
      case "rejected":
        return t("articles.statusRejected");
      case "scheduled":
        return t("articles.statusScheduled");
      case "published":
        return t("articles.statusPublished");
      default:
        return t("articles.statusDraft");
    }
  }

  if (loading) {
    return <LoadingState />;
  }

  return (
    <section className="page">
      <header className="page-header row-header">
        <div>
          <h1>{isNew ? t("articles.new") : t("articles.edit")}</h1>
          <p className="muted">{t("articles.editorSubtitle")}</p>
          {!isNew ? (
            <p className="inline-meta">
              <span className="badge">{statusLabel(status)}</span>
              {reviewComment ? <span className="muted">{t("articles.rejectionComment")}: {reviewComment}</span> : null}
              {scheduledAt ? <span className="muted">{t("articles.scheduledAt")}: {scheduledAt}</span> : null}
            </p>
          ) : null}
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

      <div className="editor-layout">
        <form className="editor-form" onSubmit={(event) => void handleSaveDraft(event)}>
          <label>
            {t("articles.fieldTitle")}
            <input value={title} onChange={(event) => setTitle(event.target.value)} required disabled={!canEditContent} />
          </label>

          <label>
            {t("articles.fieldContent")}
            <ArticleEditor content={content} onChange={setContent} />
          </label>

          {error ? <p className="error-text">{error}</p> : null}

          {canEditContent ? (
            <div className="form-actions">
              <button type="submit" className="ghost-button" disabled={saving}>
                {t("articles.saveDraft")}
              </button>
              <button type="button" className="primary-button" disabled={saving} onClick={(event) => void handleSubmitReview(event)}>
                {t("articles.submitReview")}
              </button>
            </div>
          ) : null}
        </form>

        <AiAssistPanel
          title={title}
          content={content}
          disabled={!canEditContent}
          onApplyTranslation={({ title: nextTitle, content: nextContent }) => {
            setTitle(nextTitle);
            setContent(nextContent);
          }}
        />
      </div>

      {!isNew && id ? <VersionHistoryPanel entityType="article" entityId={id} /> : null}
    </section>
  );
}
