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
const TIMEOUT_MESSAGE = "Request timed out. Please try again.";

export function ReputationPage() {
  const { t, i18n } = useTranslation();
  const { canEdit } = usePermissions();
  const [summary, setSummary] = useState<ReputationSummary | null>(null);
  const [items, setItems] = useState<ReputationMention[]>([]);
  const [sentiment, setSentiment] = useState("negative");
  const [query, setQuery] = useState("");
  const [seenFrom, setSeenFrom] = useState("");
  const [seenTo, setSeenTo] = useState("");
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

  function errorMessage(err: unknown) {
    if (err instanceof Error && err.message === TIMEOUT_MESSAGE) {
      return t("common.timeout");
    }
    return err instanceof Error ? err.message : t("common.error");
  }

  async function load(options?: { silent?: boolean }) {
    const silent = Boolean(options?.silent);
    if (!silent) {
      setLoading(true);
      setError("");
    }
    try {
      const [nextSummary, nextItems] = await Promise.all([
        fetchReputationSummary(),
        fetchReputationMentions({
          sentiment: sentiment || undefined,
          q: query || undefined,
          seen_from: seenFrom || undefined,
          seen_to: seenTo || undefined,
        }),
      ]);
      setSummary(nextSummary);
      setItems(nextItems);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [sentiment, seenFrom, seenTo]);

  useEffect(() => {
    if (summary?.last_run?.status !== "running") {
      setCrawling(false);
      return;
    }
    setCrawling(true);
    const timer = window.setInterval(() => {
      void fetchReputationSummary()
        .then((nextSummary) => {
          setSummary(nextSummary);
          const status = nextSummary.last_run?.status;
          if (!status || status === "running") {
            return;
          }
          if (status === "ok") {
            setNotice(
              t("reputation.crawlDone", {
                found: nextSummary.last_run?.found ?? 0,
                negative: nextSummary.last_run?.negative ?? 0,
              }),
            );
          } else {
            setError(
              nextSummary.last_run?.error === "timed_out"
                ? t("reputation.crawlTimeout")
                : t("reputation.crawlFailed"),
            );
          }
          void load({ silent: true });
        })
        .catch(() => undefined);
    }, 1000);
    return () => window.clearInterval(timer);
  }, [summary?.last_run?.status]);

  async function crawl() {
    setCrawling(true);
    setError("");
    setNotice("");
    try {
      const run = await runReputationCrawl();
      setSummary((current) =>
        current
          ? { ...current, last_run: run }
          : {
              total: 0,
              negative: 0,
              positive: 0,
              neutral: 0,
              open_deletion_requests: 0,
              last_run: run,
            },
      );
    } catch (err) {
      setCrawling(false);
      setError(errorMessage(err));
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
      await load({ silent: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusyId("");
    }
  }

  async function closeRequest(requestId: string) {
    setBusyId(requestId);
    try {
      await closeReputationDeletion(requestId);
      setNotice(t("reputation.deletionClosed"));
      await load({ silent: true });
    } catch (err) {
      setError(errorMessage(err));
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
              {crawling ? t("reputation.crawlRunning") : t("reputation.runCrawl")}
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
          {t("reputation.lastRun")}:{" "}
          {t(`reputation.runStatuses.${summary.last_run.status}`, {
            defaultValue: summary.last_run.status,
          })}{" "}
          · {summary.last_run.found} {t("reputation.hits")}
          {summary.last_run.finished_at
            ? ` · ${new Date(summary.last_run.finished_at).toLocaleString(i18n.language)}`
            : crawling
              ? ` · ${t("reputation.crawlRunning")}`
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
        <label className="toolbar-field">
          <span>{t("reputation.seenFrom")}</span>
          <input
            type="date"
            value={seenFrom}
            onChange={(event) => setSeenFrom(event.target.value)}
            aria-label={t("reputation.seenFrom")}
          />
        </label>
        <label className="toolbar-field">
          <span>{t("reputation.seenTo")}</span>
          <input
            type="date"
            value={seenTo}
            onChange={(event) => setSeenTo(event.target.value)}
            aria-label={t("reputation.seenTo")}
          />
        </label>
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

      {loading && items.length === 0 ? <LoadingState /> : null}
      {loading && items.length > 0 ? <p className="muted">{t("common.loading")}</p> : null}
      {error ? <p className="error-text">{error}</p> : null}
      {notice ? <p className="success-text">{notice}</p> : null}
      {letter ? (
        <pre className="reputation-letter">
          {letter}
        </pre>
      ) : null}
      {!loading && items.length === 0 ? (
        <EmptyState
          message={query || seenFrom || seenTo ? t("reputation.emptyFiltered") : t("reputation.empty")}
          icon="⌕"
        />
      ) : null}

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
                {item.source_host} ·{" "}
                {t(`reputation.channels.${item.channel}`, { defaultValue: item.channel })} · {item.query}
                {item.last_seen_at
                  ? ` · ${new Date(item.last_seen_at).toLocaleDateString(i18n.language)}`
                  : ""}
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
