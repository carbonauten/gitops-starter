import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  closeReputationDeletion,
  fetchReputationMentions,
  fetchReputationSummary,
  requestReputationDeletion,
  runReputationCrawl,
  type ReputationMention,
  type ReputationSummary,
} from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";
import { usePermissions } from "../hooks/usePermissions";

const SENTIMENTS = ["negative", "neutral", "positive"] as const;
const REASONS = ["gdpr", "inaccurate", "defamation", "other"] as const;

export function ReputationPage() {
  const { t, i18n } = useTranslation();
  const { canEdit } = usePermissions();
  const [summary, setSummary] = useState<ReputationSummary | null>(null);
  const [items, setItems] = useState<ReputationMention[]>([]);
  const [sentiment, setSentiment] = useState("negative");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [crawling, setCrawling] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [activeId, setActiveId] = useState("");
  const [reason, setReason] = useState("inaccurate");
  const [notes, setNotes] = useState("");
  const [publisherEmail, setPublisherEmail] = useState("");
  const [busyId, setBusyId] = useState("");
  const [letter, setLetter] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [nextSummary, nextItems] = await Promise.all([
        fetchReputationSummary(),
        fetchReputationMentions({ sentiment: sentiment || undefined, q: query || undefined }),
      ]);
      setSummary(nextSummary);
      setItems(nextItems);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [sentiment]);

  async function crawl() {
    setCrawling(true);
    setError("");
    setNotice("");
    try {
      const run = await runReputationCrawl();
      setNotice(
        t("reputation.crawlDone", {
          found: run.found,
          negative: run.negative,
        }),
      );
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setCrawling(false);
    }
  }

  async function submitDeletion(item: ReputationMention) {
    setBusyId(item.id);
    setError("");
    setNotice("");
    try {
      const result = await requestReputationDeletion(item.id, {
        reason,
        notes,
        publisher_email: publisherEmail,
      });
      setLetter(result.request.letter);
      setNotice(t("reputation.deletionRequested"));
      setActiveId("");
      setNotes("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusyId("");
    }
  }

  async function closeRequest(requestId: string) {
    setBusyId(requestId);
    try {
      await closeReputationDeletion(requestId);
      setNotice(t("reputation.deletionClosed"));
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusyId("");
    }
  }

  return (
    <section className="page">
      <header className="page-header row-header">
        <div>
          <p className="eyebrow">{t("reputation.eyebrow")}</p>
          <h1>{t("reputation.title")}</h1>
          <p className="muted">{t("reputation.subtitle")}</p>
        </div>
        {canEdit ? (
          <div className="header-actions">
            <button type="button" className="primary-button" disabled={crawling} onClick={() => void crawl()}>
              {crawling ? t("common.loading") : t("reputation.runCrawl")}
            </button>
          </div>
        ) : null}
      </header>

      <div className="card-grid compact-grid">
        <article className="stat-card">
          <p className="stat-label">{t("reputation.statTotal")}</p>
          <p className="stat-value">{summary?.total ?? "—"}</p>
        </article>
        <article className="stat-card">
          <p className="stat-label">{t("reputation.statNegative")}</p>
          <p className="stat-value">{summary?.negative ?? "—"}</p>
        </article>
        <article className="stat-card">
          <p className="stat-label">{t("reputation.statOpenRequests")}</p>
          <p className="stat-value">{summary?.open_deletion_requests ?? "—"}</p>
        </article>
      </div>

      {summary?.last_run ? (
        <p className="muted">
          {t("reputation.lastRun")}: {summary.last_run.status} · {summary.last_run.found}{" "}
          {t("reputation.hits")}
          {summary.last_run.finished_at
            ? ` · ${new Date(summary.last_run.finished_at).toLocaleString(i18n.language)}`
            : ""}
        </p>
      ) : null}

      <div className="toolbar">
        <select value={sentiment} onChange={(event) => setSentiment(event.target.value)}>
          <option value="">{t("reputation.allSentiments")}</option>
          {SENTIMENTS.map((item) => (
            <option key={item} value={item}>
              {t(`reputation.sentiments.${item}`)}
            </option>
          ))}
        </select>
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t("reputation.searchPlaceholder")}
          onKeyDown={(event) => {
            if (event.key === "Enter") void load();
          }}
        />
        <button type="button" className="ghost-button" onClick={() => void load()}>
          {t("reputation.applyFilter")}
        </button>
      </div>

      {loading ? <LoadingState /> : null}
      {error ? <p className="error-text">{error}</p> : null}
      {notice ? <p className="success-text">{notice}</p> : null}
      {letter ? (
        <pre className="reputation-letter">
          {letter}
        </pre>
      ) : null}
      {!loading && items.length === 0 ? <EmptyState message={t("reputation.empty")} icon="⌕" /> : null}

      <div className="list-stack">
        {items.map((item) => (
          <article key={item.id} className="list-card">
            <div>
              <div className="list-card-title-row">
                <h2>
                  <a href={item.url} target="_blank" rel="noreferrer">
                    {item.title || item.url}
                  </a>
                </h2>
                <span
                  className={
                    item.sentiment === "negative"
                      ? "workflow-badge workflow-badge-rejected"
                      : item.sentiment === "positive"
                        ? "workflow-badge workflow-badge-published"
                        : "workflow-badge workflow-badge-review"
                  }
                >
                  {t(`reputation.sentiments.${item.sentiment}`, { defaultValue: item.sentiment })}
                </span>
              </div>
              <p className="muted">
                {item.source_host} · {item.channel} · {item.query}
                {item.sentiment_reasons ? ` · ${item.sentiment_reasons}` : ""}
              </p>
              <p>{item.snippet || item.excerpt}</p>
              {item.deletion ? (
                <p className="muted">
                  {t("reputation.deletionStatus")}:{" "}
                  {t(`reputation.deletionStatuses.${item.deletion.status}`, {
                    defaultValue: item.deletion.status,
                  })}
                </p>
              ) : null}
            </div>

            {canEdit && activeId === item.id ? (
              <div className="order-ship-form">
                <label>
                  {t("reputation.deletionReason")}
                  <select value={reason} onChange={(event) => setReason(event.target.value)}>
                    {REASONS.map((value) => (
                      <option key={value} value={value}>
                        {t(`reputation.reasons.${value}`)}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  {t("reputation.publisherEmail")}
                  <input
                    value={publisherEmail}
                    onChange={(event) => setPublisherEmail(event.target.value)}
                    placeholder="datenschutz@…"
                  />
                </label>
                <label style={{ gridColumn: "1 / -1" }}>
                  {t("reputation.deletionNotes")}
                  <textarea rows={3} value={notes} onChange={(event) => setNotes(event.target.value)} />
                </label>
                <div className="list-card-actions">
                  <button
                    type="button"
                    className="primary-button"
                    disabled={busyId === item.id}
                    onClick={() => void submitDeletion(item)}
                  >
                    {t("reputation.submitDeletion")}
                  </button>
                  <button type="button" className="ghost-button" onClick={() => setActiveId("")}>
                    {t("common.cancel")}
                  </button>
                </div>
              </div>
            ) : (
              <div className="list-card-actions">
                <a href={item.url} className="ghost-button link-button" target="_blank" rel="noreferrer">
                  {t("reputation.openSource")}
                </a>
                {canEdit && !item.deletion ? (
                  <button
                    type="button"
                    className="primary-button"
                    onClick={() => {
                      setActiveId(item.id);
                      setPublisherEmail("");
                      setLetter("");
                    }}
                  >
                    {t("reputation.requestDeletion")}
                  </button>
                ) : null}
                {canEdit && item.deletion && item.deletion.status !== "closed" ? (
                  <button
                    type="button"
                    className="ghost-button"
                    disabled={busyId === item.deletion.id}
                    onClick={() => void closeRequest(item.deletion!.id)}
                  >
                    {t("reputation.closeDeletion")}
                  </button>
                ) : null}
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
