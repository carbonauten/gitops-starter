import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { fetchAnalyticsOverview, type AnalyticsOverview } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";

const RANGE_OPTIONS = [30, 90, 180] as const;

function articleStatusLabelKey(status: string): string {
  switch (status) {
    case "published":
      return "articles.statusPublished";
    case "review":
      return "articles.statusReview";
    case "rejected":
      return "articles.statusRejected";
    case "scheduled":
      return "articles.statusScheduled";
    default:
      return "articles.statusDraft";
  }
}

function maxCount(items: Array<{ count: number }>): number {
  return Math.max(1, ...items.map((item) => item.count));
}

function entriesFromRecord(record: Record<string, number>): Array<{ key: string; count: number }> {
  return Object.entries(record)
    .map(([key, count]) => ({ key, count }))
    .sort((a, b) => b.count - a.count);
}

function BarList({
  items,
  labelFor,
}: {
  items: Array<{ key: string; count: number }>;
  labelFor: (key: string) => string;
}) {
  const peak = maxCount(items);
  if (items.length === 0) {
    return null;
  }
  return (
    <ul className="analytics-bar-list">
      {items.map((item) => (
        <li key={item.key}>
          <div className="analytics-bar-meta">
            <span>{labelFor(item.key)}</span>
            <strong>{item.count}</strong>
          </div>
          <div className="analytics-bar-track" aria-hidden="true">
            <div className="analytics-bar-fill" style={{ width: `${Math.round((item.count / peak) * 100)}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

export function AnalyticsPage() {
  const { t } = useTranslation();
  const [days, setDays] = useState<number>(90);
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setLoading(true);
      try {
        const payload = await fetchAnalyticsOverview(days);
        if (!cancelled) {
          setOverview(payload);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [days]);

  const sparkDays = useMemo(() => {
    if (!overview) {
      return [];
    }
    // Show last 30 points of the selected range for readability
    return overview.publications.by_day.slice(-30);
  }, [overview]);

  const sparkPeak = maxCount(sparkDays);

  return (
    <section className="page">
      <header className="page-header analytics-header">
        <div>
          <p className="eyebrow">{t("analytics.eyebrow")}</p>
          <h1>{t("analytics.title")}</h1>
          <p className="muted">{t("analytics.subtitle")}</p>
        </div>
        <div className="analytics-range" role="group" aria-label={t("analytics.rangeLabel")}>
          {RANGE_OPTIONS.map((option) => (
            <button
              key={option}
              type="button"
              className={days === option ? "primary-button" : "ghost-button"}
              onClick={() => setDays(option)}
            >
              {t("analytics.rangeDays", { days: option })}
            </button>
          ))}
        </div>
      </header>

      {loading ? <LoadingState /> : null}
      {!loading && !overview ? <EmptyState message={t("analytics.empty")} icon="▥" /> : null}

      {!loading && overview ? (
        <>
          <div className="card-grid">
            <article className="stat-card">
              <p className="stat-value">{overview.articles.total}</p>
              <p className="stat-label">{t("analytics.kpi.articles")}</p>
            </article>
            <article className="stat-card">
              <p className="stat-value">{overview.certificates.total}</p>
              <p className="stat-label">{t("analytics.kpi.certificates")}</p>
            </article>
            <article className="stat-card">
              <p className="stat-value">{overview.publications.in_range}</p>
              <p className="stat-label">{t("analytics.kpi.publications")}</p>
            </article>
            <article className="stat-card">
              <p className="stat-value">{overview.files.total}</p>
              <p className="stat-label">{t("analytics.kpi.files")}</p>
            </article>
            <article className="stat-card">
              <p className="stat-value">{overview.certificates.expiring_30}</p>
              <p className="stat-label">{t("analytics.kpi.expiring30")}</p>
            </article>
            <article className="stat-card">
              <p className="stat-value">{overview.activity.audit_actions_in_range}</p>
              <p className="stat-label">{t("analytics.kpi.audit")}</p>
            </article>
          </div>

          <div className="home-grid analytics-grid">
            <section className="home-panel">
              <div className="home-panel-head">
                <h2>{t("analytics.articlesByStatus")}</h2>
                <Link to="/articles" className="muted">
                  {t("analytics.openArticles")}
                </Link>
              </div>
              {entriesFromRecord(overview.articles.by_status).length === 0 ? (
                <p className="muted">{t("analytics.noData")}</p>
              ) : (
                <BarList
                  items={entriesFromRecord(overview.articles.by_status)}
                  labelFor={(key) => t(articleStatusLabelKey(key))}
                />
              )}
            </section>

            <section className="home-panel">
              <div className="home-panel-head">
                <h2>{t("analytics.certificatesByStatus")}</h2>
                <Link to="/certificates" className="muted">
                  {t("analytics.openCertificates")}
                </Link>
              </div>
              {entriesFromRecord(overview.certificates.by_status).length === 0 ? (
                <p className="muted">{t("analytics.noData")}</p>
              ) : (
                <BarList
                  items={entriesFromRecord(overview.certificates.by_status)}
                  labelFor={(key) => t(`certificates.status.${key}`, { defaultValue: key })}
                />
              )}
              <div className="analytics-mini-kpis">
                <span>
                  {t("analytics.expiring60")}: <strong>{overview.certificates.expiring_60}</strong>
                </span>
                <span>
                  {t("analytics.expiring90")}: <strong>{overview.certificates.expiring_90}</strong>
                </span>
                <span>
                  {t("analytics.renewalsPending")}: <strong>{overview.certificates.renewals_pending}</strong>
                </span>
              </div>
            </section>

            <section className="home-panel">
              <div className="home-panel-head">
                <h2>{t("analytics.certificatesByCategory")}</h2>
              </div>
              {entriesFromRecord(overview.certificates.by_category).length === 0 ? (
                <p className="muted">{t("analytics.noData")}</p>
              ) : (
                <BarList
                  items={entriesFromRecord(overview.certificates.by_category)}
                  labelFor={(key) => t(`certificates.categories.${key}`, { defaultValue: key })}
                />
              )}
            </section>

            <section className="home-panel">
              <div className="home-panel-head">
                <h2>{t("analytics.deliveriesByChannel")}</h2>
                <Link to="/publish" className="muted">
                  {t("analytics.openPublish")}
                </Link>
              </div>
              {overview.publications.deliveries.by_channel.length === 0 ? (
                <p className="muted">{t("analytics.noData")}</p>
              ) : (
                <ul className="analytics-bar-list">
                  {overview.publications.deliveries.by_channel.map((channel) => {
                    const peak = Math.max(1, channel.total);
                    return (
                      <li key={channel.channel}>
                        <div className="analytics-bar-meta">
                          <span>{t(`publish.channels.${channel.channel}`, { defaultValue: channel.channel })}</span>
                          <strong>
                            {channel.sent}/{channel.total}
                          </strong>
                        </div>
                        <div className="analytics-bar-track analytics-bar-track-split" aria-hidden="true">
                          <div
                            className="analytics-bar-fill analytics-bar-fill-ok"
                            style={{ width: `${Math.round((channel.sent / peak) * 100)}%` }}
                          />
                          <div
                            className="analytics-bar-fill analytics-bar-fill-fail"
                            style={{ width: `${Math.round((channel.failed / peak) * 100)}%` }}
                          />
                        </div>
                        <p className="muted analytics-channel-detail">
                          {t("analytics.channelDetail", {
                            sent: channel.sent,
                            failed: channel.failed,
                            pending: channel.pending,
                          })}
                        </p>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>

            <section className="home-panel analytics-span-2">
              <div className="home-panel-head">
                <h2>{t("analytics.publishTrend")}</h2>
                <span className="muted">{t("analytics.last30DaysChart")}</span>
              </div>
              {sparkDays.every((day) => day.count === 0) ? (
                <p className="muted">{t("analytics.noData")}</p>
              ) : (
                <div className="analytics-spark" role="img" aria-label={t("analytics.publishTrend")}>
                  {sparkDays.map((day) => (
                    <div key={day.date} className="analytics-spark-col" title={`${day.date}: ${day.count}`}>
                      <div
                        className="analytics-spark-bar"
                        style={{ height: `${Math.max(4, Math.round((day.count / sparkPeak) * 100))}%` }}
                      />
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className="home-panel">
              <div className="home-panel-head">
                <h2>{t("analytics.topAuthors")}</h2>
              </div>
              {overview.activity.top_authors.length === 0 ? (
                <p className="muted">{t("analytics.noData")}</p>
              ) : (
                <div className="list-stack">
                  {overview.activity.top_authors.map((author) => (
                    <div key={author.author_name} className="home-item">
                      <strong>{author.author_name}</strong>
                      <span className="muted">
                        {t("analytics.authorArticles", { count: author.article_count })}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className="home-panel">
              <div className="home-panel-head">
                <h2>{t("analytics.recentPublications")}</h2>
              </div>
              {overview.publications.recent.length === 0 ? (
                <p className="muted">{t("analytics.noData")}</p>
              ) : (
                <div className="list-stack">
                  {overview.publications.recent.map((item) => (
                    <div key={item.id} className="home-item">
                      <strong>{item.title || t("analytics.untitled")}</strong>
                      <span className="muted">
                        {item.published_by_name}
                        {item.created_at ? ` · ${new Date(item.created_at).toLocaleString()}` : ""}
                        {` · ${item.channels_ok}/${item.channels_total}`}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        </>
      ) : null}
    </section>
  );
}
