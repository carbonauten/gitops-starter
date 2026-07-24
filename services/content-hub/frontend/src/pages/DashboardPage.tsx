import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import {
  fetchDashboardHome,
  fetchDashboardStats,
  fetchPlatformInfo,
  fetchSyncStatus,
  runRegionSync,
  type DashboardHome,
  type DashboardStats,
  type PlatformInfo,
  type SyncStatus,
} from "../api/client";
import { GlobalSearch } from "../components/GlobalSearch";
import { LoadingState } from "../components/LoadingState";
import { OnboardingTips } from "../components/OnboardingTips";
import { PublishCalendarPanel } from "../components/PublishCalendarPanel";
import { usePermissions } from "../hooks/usePermissions";

export function DashboardPage() {
  const { t } = useTranslation();
  const { isItMaster, canApprove, canApproveCertificates } = usePermissions();
  const [stats, setStats] = useState<DashboardStats>({
    drafts: 0,
    in_review: 0,
    scheduled: 0,
    published: 0,
    files: 0,
    certificates: 0,
    renewals_pending: 0,
    expiring_30: 0,
    expiring_60: 0,
    expiring_90: 0,
  });
  const [home, setHome] = useState<DashboardHome | null>(null);
  const [platform, setPlatform] = useState<PlatformInfo | null>(null);
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);
  const [syncRunning, setSyncRunning] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      try {
        const [statsPayload, platformPayload, homePayload] = await Promise.all([
          fetchDashboardStats(),
          fetchPlatformInfo(),
          fetchDashboardHome(),
        ]);
        setStats(statsPayload);
        setPlatform(platformPayload);
        setHome(homePayload);
        if (isItMaster) {
          try {
            setSyncStatus(await fetchSyncStatus());
          } catch {
            setSyncStatus(null);
          }
        }
      } finally {
        setLoading(false);
      }
    })();
  }, [isItMaster]);

  const cards = [
    { label: t("dashboard.drafts"), value: stats.drafts, to: "/articles?status=draft" },
    { label: t("dashboard.inReview"), value: stats.in_review, to: "/workflow" },
    { label: t("dashboard.scheduled"), value: stats.scheduled, to: "/publish/calendar" },
    { label: t("dashboard.published"), value: stats.published, to: "/articles" },
    { label: t("dashboard.files"), value: stats.files, to: "/files" },
    { label: t("dashboard.certificates"), value: stats.certificates, to: "/certificates" },
  ];

  const expiryCards = [
    { label: t("dashboard.expiring30"), value: stats.expiring_30 },
    { label: t("dashboard.expiring60"), value: stats.expiring_60 },
    { label: t("dashboard.expiring90"), value: stats.expiring_90 },
  ];

  const regionLabel =
    platform?.deployment_region === "cn" ? t("dashboard.regionCn") : t("dashboard.regionEu");
  const storageLabel =
    platform?.storage_backend === "oss" ? t("dashboard.storageOss") : t("dashboard.storageLocal");

  async function handleRunSync() {
    setSyncRunning(true);
    try {
      await runRegionSync();
      setSyncStatus(await fetchSyncStatus());
    } finally {
      setSyncRunning(false);
    }
  }

  return (
    <section className="page">
      <header className="page-header dashboard-search-hero">
        <div>
          <p className="eyebrow">{t("dashboard.myHome")}</p>
          <h1>
            {home?.greeting_name
              ? t("dashboard.greeting", { name: home.greeting_name })
              : t("dashboard.title")}
          </h1>
          <p className="muted">{t("dashboard.subtitleHome")}</p>
        </div>
        <GlobalSearch variant="hero" />
      </header>

      {loading ? <LoadingState /> : null}

      <OnboardingTips />

      {home ? (
        <div className="home-grid">
          <section className="home-panel">
            <div className="home-panel-head">
              <h2>{t("dashboard.myDrafts")}</h2>
              <Link to="/articles" className="muted">
                {t("dashboard.viewAll")}
              </Link>
            </div>
            {home.my_drafts.length === 0 ? (
              <p className="muted">{t("dashboard.emptyDrafts")}</p>
            ) : (
              <div className="list-stack">
                {home.my_drafts.map((item) => (
                  <Link key={item.id} to={`/articles/${item.id}/edit`} className="home-item">
                    <strong>{item.title}</strong>
                    <span className="muted">{item.status}</span>
                  </Link>
                ))}
              </div>
            )}
          </section>

          <section className="home-panel">
            <div className="home-panel-head">
              <h2>{t("dashboard.myApprovals")}</h2>
              {(canApprove || canApproveCertificates) ? (
                <Link to="/workflow" className="muted">
                  {t("dashboard.workflowLink")}
                </Link>
              ) : null}
            </div>
            {home.my_approvals.length === 0 ? (
              <p className="muted">{t("dashboard.emptyApprovals")}</p>
            ) : (
              <div className="list-stack">
                {home.my_approvals.map((item) => (
                  <Link
                    key={`${item.kind}-${item.id}`}
                    to={
                      item.kind === "certificate_renewal"
                        ? `/certificates/${item.id}/edit`
                        : `/articles/${item.id}/edit`
                    }
                    className="home-item"
                  >
                    <strong>{item.title || item.name}</strong>
                    <span className="muted">{item.kind}</span>
                  </Link>
                ))}
              </div>
            )}
          </section>

          <section className="home-panel">
            <div className="home-panel-head">
              <h2>{t("dashboard.myExpiring")}</h2>
              <Link to="/certificates" className="muted">
                {t("dashboard.viewAll")}
              </Link>
            </div>
            {home.my_expiring_certificates.length === 0 ? (
              <p className="muted">{t("dashboard.emptyExpiring")}</p>
            ) : (
              <div className="list-stack">
                {home.my_expiring_certificates.map((item) => (
                  <Link key={item.id} to={`/certificates/${item.id}/edit`} className="home-item">
                    <strong>{item.name}</strong>
                    <span className="muted">
                      {item.valid_to} · {item.days_until_expiry}d
                    </span>
                  </Link>
                ))}
              </div>
            )}
          </section>

          <section className="home-panel">
            <div className="home-panel-head">
              <h2>{t("dashboard.whatsNew")}</h2>
              <Link to="/publish" className="muted">
                {t("dashboard.viewAll")}
              </Link>
            </div>
            {home.recent_publications.length === 0 ? (
              <p className="muted">{t("dashboard.emptyWhatsNew")}</p>
            ) : (
              <div className="list-stack">
                {home.recent_publications.map((item) => (
                  <div key={item.id} className="home-item">
                    <strong>{item.title}</strong>
                    <span className="muted">
                      {item.published_by_name}
                      {item.created_at ? ` · ${new Date(item.created_at).toLocaleString()}` : ""}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      ) : null}

      <div className="section-block">
        <PublishCalendarPanel compact />
      </div>

      {platform ? (
        <div className="section-block">
          <h2>{t("dashboard.regionTitle")}</h2>
          <div className="inline-meta">
            <span className="badge">{regionLabel}</span>
            <span className="muted">{storageLabel}</span>
          </div>
        </div>
      ) : null}

      <div className="card-grid">
        {cards.map((card) => (
          <Link key={card.label} to={card.to} className="stat-card stat-card-link">
            <p className="stat-value">{card.value}</p>
            <p className="stat-label">{card.label}</p>
          </Link>
        ))}
      </div>

      <div className="section-block">
        <h2>{t("dashboard.expiringTitle")}</h2>
        <div className="card-grid compact-grid">
          {expiryCards.map((card) => (
            <Link key={card.label} to="/certificates" className="stat-card stat-card-link">
              <p className="stat-value">{card.value}</p>
              <p className="stat-label">{card.label}</p>
            </Link>
          ))}
        </div>
      </div>

      {isItMaster && syncStatus ? (
        <div className="section-block">
          <h2>{t("dashboard.syncTitle")}</h2>
          <p className="muted">
            {syncStatus.sync_enabled ? t("dashboard.syncEnabled") : t("dashboard.syncDisabled")}
            {syncStatus.sync_enabled ? ` · ${t("dashboard.syncPeer")}: ${syncStatus.peer_region.toUpperCase()}` : null}
          </p>
          <dl className="meta-list">
            <div>
              <dt>{t("dashboard.syncLastSuccess")}</dt>
              <dd>{syncStatus.last_success_at ?? t("dashboard.syncNever")}</dd>
            </div>
            {syncStatus.last_failure_at ? (
              <div>
                <dt>{t("dashboard.syncLastFailure")}</dt>
                <dd>{syncStatus.last_failure_message ?? syncStatus.last_failure_at}</dd>
              </div>
            ) : null}
          </dl>
          {syncStatus.sync_enabled ? (
            <button type="button" className="primary-button" disabled={syncRunning} onClick={() => void handleRunSync()}>
              {syncRunning ? t("dashboard.syncRunning") : t("dashboard.syncRun")}
            </button>
          ) : null}
        </div>
      ) : null}

      <div className="info-banner platform-tip">{t("dashboard.platformTip")}</div>
    </section>
  );
}
