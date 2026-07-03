import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import {
  fetchDashboardStats,
  fetchPlatformInfo,
  fetchSyncStatus,
  runRegionSync,
  type DashboardStats,
  type PlatformInfo,
  type SyncStatus,
} from "../api/client";
import { OnboardingTips } from "../components/OnboardingTips";
import { GlobalSearch } from "../components/GlobalSearch";
import { LoadingState } from "../components/LoadingState";
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
  const [platform, setPlatform] = useState<PlatformInfo | null>(null);
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);
  const [syncRunning, setSyncRunning] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      try {
        const [statsPayload, platformPayload] = await Promise.all([
          fetchDashboardStats(),
          fetchPlatformInfo(),
        ]);
        setStats(statsPayload);
        setPlatform(platformPayload);
        if (isItMaster) {
          try {
            const syncPayload = await fetchSyncStatus();
            setSyncStatus(syncPayload);
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
    { label: t("dashboard.drafts"), value: stats.drafts, to: "/articles" },
    { label: t("dashboard.inReview"), value: stats.in_review, to: "/workflow" },
    { label: t("dashboard.scheduled"), value: stats.scheduled, to: "/workflow" },
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
      const syncPayload = await fetchSyncStatus();
      setSyncStatus(syncPayload);
    } finally {
      setSyncRunning(false);
    }
  }

  return (
    <section className="page">
      <header className="page-header dashboard-search-hero">
        <div>
          <h1>{t("dashboard.title")}</h1>
          <p className="muted">{t("dashboard.subtitle")}</p>
        </div>
        <GlobalSearch variant="hero" />
      </header>

      {loading ? <LoadingState /> : null}

      <OnboardingTips />

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

      {(canApprove || canApproveCertificates) && (stats.in_review > 0 || stats.renewals_pending > 0) ? (
        <div className="section-block">
          <h2>{t("dashboard.workflowTitle")}</h2>
          <p className="muted">
            {stats.in_review} {t("dashboard.inReview")} · {stats.renewals_pending} {t("dashboard.renewalsPending")}
          </p>
          <Link to="/workflow" className="primary-button link-button">
            {t("dashboard.workflowLink")}
          </Link>
        </div>
      ) : null}

      <div className="info-banner platform-tip">{t("dashboard.platformTip")}</div>
    </section>
  );
}
