import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import {
  fetchAiStatus,
  fetchOutlookMail,
  fetchOutlookMailMessage,
  saveOutlookMail,
  summarizeOutlookMail,
  type OutlookMailMessage,
  type OutlookMailSummary,
} from "../api/client";

type Props = {
  connected: boolean;
};

export function OutlookMailPanel({ connected }: Props) {
  const { t, i18n } = useTranslation();
  const [messages, setMessages] = useState<OutlookMailSummary[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [detail, setDetail] = useState<OutlookMailMessage | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [savedArticleId, setSavedArticleId] = useState("");
  const [aiAvailable, setAiAvailable] = useState(false);
  const [summarizing, setSummarizing] = useState(false);
  const [summary, setSummary] = useState("");
  const [summaryError, setSummaryError] = useState("");

  useEffect(() => {
    void (async () => {
      try {
        setAiAvailable((await fetchAiStatus()).available);
      } catch {
        setAiAvailable(false);
      }
    })();
  }, []);

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
    setSummary("");
    setSummaryError("");
    try {
      setDetail(await fetchOutlookMailMessage(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    }
  }

  async function handleSummarize() {
    if (!selectedId) return;
    setSummarizing(true);
    setSummaryError("");
    try {
      const uiLanguage = (["de", "en", "zh-CN"].includes(i18n.language) ? i18n.language : "de") as
        | "de"
        | "en"
        | "zh-CN";
      setSummary(await summarizeOutlookMail(selectedId, uiLanguage));
    } catch (err) {
      setSummaryError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setSummarizing(false);
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
      setNotice(t("mail.saved"));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setSaving(false);
    }
  }

  if (!connected) {
    return (
      <section className="outlook-mail-panel">
        <p className="muted">{t("mail.connectFirst")}</p>
      </section>
    );
  }

  return (
    <section className="outlook-mail-panel">
      <header className="outlook-mail-header">
        <div>
          <h2>{t("mail.inboxTitle")}</h2>
          <p className="muted">{t("mail.inboxSubtitle")}</p>
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
            placeholder={t("mail.searchPlaceholder")}
            aria-label={t("mail.searchPlaceholder")}
          />
          <button type="submit" className="ghost-button" disabled={loading}>
            {t("mail.search")}
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
              <Link to={`/articles/${savedArticleId}/edit`}>{t("mail.openArticle")}</Link>
            </>
          ) : null}
        </p>
      ) : null}

      <div className="outlook-mail-layout">
        <div className="outlook-mail-list-pane">
          {loading ? <p className="muted">{t("common.loading")}</p> : null}
          {!loading && messages.length === 0 ? (
            <p className="muted">{t("mail.empty")}</p>
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
            <p className="muted">{t("mail.selectHint")}</p>
          ) : (
            <>
              <div className="outlook-mail-detail-actions">
                <button
                  type="button"
                  className="primary-button"
                  disabled={saving}
                  onClick={() => void handleSave()}
                >
                  {saving ? t("common.loading") : t("mail.save")}
                </button>
                {detail.web_link ? (
                  <a
                    className="ghost-button link-button"
                    href={detail.web_link}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {t("mail.openOutlook")}
                  </a>
                ) : null}
                {aiAvailable ? (
                  <button
                    type="button"
                    className="ghost-button"
                    disabled={summarizing}
                    onClick={() => void handleSummarize()}
                  >
                    {summarizing ? t("common.loading") : t("mail.aiSummarize")}
                  </button>
                ) : null}
              </div>
              <h3>{detail.subject}</h3>
              <p className="muted">
                {t("mail.from")}: {detail.from.name || detail.from.email || "—"}
                {detail.from.name && detail.from.email ? ` <${detail.from.email}>` : ""}
              </p>
              <p className="muted">
                {t("mail.received")}: {detail.received_at || "—"}
              </p>
              {summaryError ? <p className="error-text">{summaryError}</p> : null}
              {summary ? (
                <div className="ai-summary-box">
                  <strong>{t("mail.aiSummaryTitle")}</strong>
                  <pre>{summary}</pre>
                </div>
              ) : null}
              <EmailBodyFrame body={detail.body} bodyType={detail.body_type} />
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

type EmailBodyFrameProps = {
  body: string;
  bodyType: "html" | "text";
};

/**
 * Renders untrusted email content inside a sandboxed iframe so embedded
 * <style>/<script>/event-handler payloads can't leak into or execute in the
 * host page (the previous dangerouslySetInnerHTML render allowed both).
 */
const EMAIL_FRAME_BASE_STYLES = `<style>
  html, body {
    margin: 0;
    padding: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 14px;
    line-height: 1.5;
    color: #1f2937;
    overflow-wrap: anywhere;
    word-break: break-word;
  }
  img, table, video { max-width: 100%; height: auto; }
  pre { white-space: pre-wrap; }
</style>`;

function EmailBodyFrame({ body, bodyType }: EmailBodyFrameProps) {
  const frameRef = useRef<HTMLIFrameElement>(null);
  const [height, setHeight] = useState(200);

  // The iframe's srcDoc is a separate document, so it does not inherit any
  // of the app's CSS - without this, unstyled email markup (or a plain-text
  // body) falls back to the browser's default UA stylesheet (large heading
  // sizes, no word wrapping), which is what caused the oversized/overflowing
  // text seen in the panel.
  const srcDoc =
    EMAIL_FRAME_BASE_STYLES +
    (bodyType === "html"
      ? body
      : `<pre style="white-space:pre-wrap;font-family:inherit;margin:0">${escapeHtml(body)}</pre>`);

  const resize = useCallback(() => {
    const doc = frameRef.current?.contentDocument;
    if (doc?.body) {
      setHeight(doc.body.scrollHeight + 16);
    }
  }, []);

  useEffect(() => {
    resize();
  }, [srcDoc, resize]);

  return (
    <iframe
      ref={frameRef}
      className="outlook-mail-body outlook-mail-body-frame"
      title="email-body"
      srcDoc={srcDoc}
      sandbox="allow-same-origin allow-popups"
      onLoad={resize}
      style={{ width: "100%", height, border: "none" }}
    />
  );
}
