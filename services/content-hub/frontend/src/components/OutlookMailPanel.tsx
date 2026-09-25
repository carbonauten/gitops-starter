import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import {
  fetchOutlookMail,
  fetchOutlookMailMessage,
  saveOutlookMail,
  type OutlookMailMessage,
  type OutlookMailSummary,
} from "../api/client";

type Props = {
  connected: boolean;
};

export function OutlookMailPanel({ connected }: Props) {
  const { t } = useTranslation();
  const [messages, setMessages] = useState<OutlookMailSummary[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [detail, setDetail] = useState<OutlookMailMessage | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [savedArticleId, setSavedArticleId] = useState("");

  const loadMessages = useCallback(
    async (search = "") => {
      if (!connected) {
        setMessages([]);
        return;
      }
      setLoading(true);
      setError("");
      try {
        const items = await fetchOutlookMail({ q: search, top: 30 });
        setMessages(items);
        if (selectedId && !items.some((item) => item.id === selectedId)) {
          setSelectedId("");
          setDetail(null);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : t("common.error"));
        setMessages([]);
      } finally {
        setLoading(false);
      }
    },
    [connected, selectedId, t],
  );

  useEffect(() => {
    void loadMessages("");
  }, [connected]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleSelect(id: string) {
    setSelectedId(id);
    setDetail(null);
    setError("");
    setNotice("");
    setSavedArticleId("");
    try {
      setDetail(await fetchOutlookMailMessage(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    }
  }

  async function handleSave() {
    if (!selectedId) return;
    setSaving(true);
    setError("");
    setNotice("");
    setSavedArticleId("");
    try {
      const saved = await saveOutlookMail(selectedId, "both");
      if (saved.article?.id) {
        setSavedArticleId(saved.article.id);
      }
      setNotice(t("calendar.mailSaved"));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setSaving(false);
    }
  }

  if (!connected) {
    return null;
  }

  return (
    <section className="outlook-mail-panel">
      <header className="outlook-mail-header">
        <div>
          <h2>{t("calendar.mailTitle")}</h2>
          <p className="muted">{t("calendar.mailSubtitle")}</p>
        </div>
        <form
          className="outlook-mail-search"
          onSubmit={(event) => {
            event.preventDefault();
            void loadMessages(query);
          }}
        >
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t("calendar.mailSearchPlaceholder")}
            aria-label={t("calendar.mailSearchPlaceholder")}
          />
          <button type="submit" className="ghost-button" disabled={loading}>
            {t("calendar.mailSearch")}
          </button>
        </form>
      </header>

      {error ? <p className="error-text">{error}</p> : null}
      {notice ? (
        <p className="success-text">
          {notice}
          {savedArticleId ? (
            <>
              {" "}
              <Link to={`/articles/${savedArticleId}/edit`}>{t("calendar.mailOpenArticle")}</Link>
            </>
          ) : null}
        </p>
      ) : null}

      <div className="outlook-mail-layout">
        <div className="outlook-mail-list-pane">
          {loading ? <p className="muted">{t("common.loading")}</p> : null}
          {!loading && messages.length === 0 ? (
            <p className="muted">{t("calendar.mailEmpty")}</p>
          ) : null}
          <ul className="outlook-mail-list">
            {messages.map((message) => (
              <li key={message.id}>
                <button
                  type="button"
                  className={`outlook-mail-item${selectedId === message.id ? " is-selected" : ""}${
                    message.is_read ? "" : " is-unread"
                  }`}
                  onClick={() => void handleSelect(message.id)}
                >
                  <span className="outlook-mail-item-subject">{message.subject}</span>
                  <span className="outlook-mail-item-from">
                    {message.from.name || message.from.email || "—"}
                  </span>
                  <span className="outlook-mail-item-preview muted">{message.preview}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="outlook-mail-detail-pane">
          {!detail ? (
            <p className="muted">{t("calendar.mailSelectHint")}</p>
          ) : (
            <>
              <div className="outlook-mail-detail-actions">
                <button
                  type="button"
                  className="primary-button"
                  disabled={saving}
                  onClick={() => void handleSave()}
                >
                  {saving ? t("common.loading") : t("calendar.mailSave")}
                </button>
                {detail.web_link ? (
                  <a
                    className="ghost-button link-button"
                    href={detail.web_link}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {t("calendar.mailOpenOutlook")}
                  </a>
                ) : null}
              </div>
              <h3>{detail.subject}</h3>
              <p className="muted">
                {t("calendar.mailFrom")}: {detail.from.name || detail.from.email || "—"}
                {detail.from.name && detail.from.email ? ` <${detail.from.email}>` : ""}
              </p>
              <p className="muted">
                {t("calendar.mailReceived")}: {detail.received_at || "—"}
              </p>
              <div
                className="outlook-mail-body"
                dangerouslySetInnerHTML={{
                  __html:
                    detail.body_type === "html"
                      ? detail.body
                      : `<pre style="white-space:pre-wrap;font-family:inherit">${escapeHtml(detail.body)}</pre>`,
                }}
              />
            </>
          )}
        </div>
      </div>
    </section>
  );
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}
