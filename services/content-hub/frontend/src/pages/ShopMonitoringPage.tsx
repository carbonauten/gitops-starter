import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { fetchShopMonitoringSummary, type ShopMonitoringSummary } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";

const RANGE_OPTIONS = [7, 30, 90] as const;

function maxCount(items: Array<{ count: number }>): number {
  return Math.max(1, ...items.map((item) => item.count));
}

function formatWhen(value: string | null | undefined, locale: string): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString(locale);
  } catch {
    return value;
  }
}

export function ShopMonitoringPage() {
  const { t, i18n } = useTranslation();
  const [days, setDays] = useState<number>(30);
  const [summary, setSummary] = useState<ShopMonitoringSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setLoading(true);
      setError("");
      try {
        const payload = await fetchShopMonitoringSummary(days);
        if (!cancelled) setSummary(payload);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : t("common.error"));
          setSummary(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [days, t]);

  const sparkDays = useMemo(() => summary?.by_day.slice(-30) ?? [], [summary]);
  const sparkPeak = maxCount(sparkDays);
  const pathPeak = maxCount(summary?.top_paths ?? [{ count: 1 }]);
  const ipPeak = maxCount(summary?.top_ips ?? [{ count: 1 }]);

  return (
    <section className="page">
      <header className="page-header analytics-header">
        <div>
          <p className="eyebrow">{t("shopMonitoring.eyebrow")}</p>
          <h1>{t("shopMonitoring.title")}</h1>
          <p className="muted">{t("shopMonitoring.subtitle")}</p>
        </div>
        <div className="analytics-range" role="group" aria-label={t("shopMonitoring.rangeLabel")}>
          {RANGE_OPTIONS.map((option) => (
            <button
              key={option}
              type="button"
              className={days === option ? "primary-button" : "ghost-button"}
              onClick={() => setDays(option)}
            >
              {t("shopMonitoring.rangeDays", { days: option })}
            </button>
          ))}
        </div>
      </header>

      {loading ? <LoadingState /> : null}
      {error ? <p className="error-text">{error}</p> : null}

      {!loading && summary ? (
        <>
          <div className="card-grid">
            <article className="stat-card">
              <p className="stat-value">{summary.views_today}</p>
              <p className="stat-label">{t("shopMonitoring.viewsToday")}</p>
            </article>
            <article className="stat-card">
              <p className="stat-value">{summary.views_7d}</p>
              <p className="stat-label">{t("shopMonitoring.views7d")}</p>
            </article>
            <article className="stat-card">
              <p className="stat-value">{summary.views_period}</p>
              <p className="stat-label">{t("shopMonitoring.viewsPeriod")}</p>
            </article>
            <article className="stat-card">
              <p className="stat-value">{summary.unique_visitors_period}</p>
              <p className="stat-label">{t("shopMonitoring.uniquePeriod")}</p>
            </article>
          </div>

          <div className="home-grid analytics-grid" style={{ marginTop: "1.5rem" }}>
            <section className="home-panel analytics-span-2">
              <div className="home-panel-head">
                <h2>{t("shopMonitoring.trafficTitle")}</h2>
              </div>
              <p className="muted">{t("shopMonitoring.trafficSubtitle")}</p>
              {sparkDays.every((d) => d.count === 0) ? (
                <EmptyState message={t("shopMonitoring.empty")} icon="▥" />
              ) : (
                <div className="analytics-spark" aria-hidden="true">
                  {sparkDays.map((day) => (
                    <div key={day.day} className="analytics-spark-col" title={`${day.day}: ${day.count}`}>
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
                <h2>{t("shopMonitoring.topPages")}</h2>
              </div>
              {(summary.top_paths || []).length === 0 ? (
                <p className="muted">{t("shopMonitoring.empty")}</p>
              ) : (
                <ul className="analytics-bar-list">
                  {summary.top_paths.map((item) => (
                    <li key={item.path}>
                      <div className="analytics-bar-meta">
                        <span>{item.path}</span>
                        <strong>{item.count}</strong>
                      </div>
                      <div className="analytics-bar-track" aria-hidden="true">
                        <div
                          className="analytics-bar-fill"
                          style={{ width: `${Math.round((item.count / pathPeak) * 100)}%` }}
                        />
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="home-panel">
              <div className="home-panel-head">
                <h2>{t("shopMonitoring.topIps")}</h2>
              </div>
              {(summary.top_ips || []).length === 0 ? (
                <p className="muted">{t("shopMonitoring.empty")}</p>
              ) : (
                <ul className="analytics-bar-list">
                  {(summary.top_ips || []).map((item) => (
                    <li key={item.ip}>
                      <div className="analytics-bar-meta">
                        <span>
                          <code>{item.ip}</code>
                        </span>
                        <strong>{item.count}</strong>
                      </div>
                      <div className="analytics-bar-track" aria-hidden="true">
                        <div
                          className="analytics-bar-fill"
                          style={{ width: `${Math.round((item.count / ipPeak) * 100)}%` }}
                        />
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>

          <section className="home-panel" style={{ marginTop: "1.5rem" }}>
            <div className="home-panel-head">
              <h2>{t("shopMonitoring.recentTitle")}</h2>
            </div>
            {(summary.recent || []).length === 0 ? (
              <p className="muted">{t("shopMonitoring.empty")}</p>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>{t("shopMonitoring.colWhen")}</th>
                      <th>{t("shopMonitoring.colPath")}</th>
                      <th>{t("shopMonitoring.colIp")}</th>
                      <th>{t("shopMonitoring.colReferrer")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.recent.map((row) => (
                      <tr key={row.id}>
                        <td>{formatWhen(row.created_at, i18n.language)}</td>
                        <td>
                          <code>{row.path}</code>
                        </td>
                        <td>
                          <code>{row.ip_address || "—"}</code>
                        </td>
                        <td className="muted">{row.referrer || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      ) : null}
    </section>
  );
}
