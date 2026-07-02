import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { fetchDashboardStats, type DashboardStats } from "../api/client";

export function DashboardPage() {
  const { t } = useTranslation();
  const [stats, setStats] = useState<DashboardStats>({
    drafts: 0,
    published: 0,
    files: 0,
    certificates: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      try {
        const payload = await fetchDashboardStats();
        setStats(payload);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const cards = [
    { label: t("dashboard.drafts"), value: stats.drafts, to: "/articles" },
    { label: t("dashboard.published"), value: stats.published, to: "/articles" },
    { label: t("dashboard.files"), value: stats.files, to: "/files" },
    { label: t("dashboard.certificates"), value: stats.certificates, to: "/certificates" },
  ];

  return (
    <section className="page">
      <header className="page-header">
        <h1>{t("dashboard.title")}</h1>
        <p className="muted">{t("dashboard.subtitle")}</p>
      </header>

      {loading ? <p>{t("common.loading")}</p> : null}

      <div className="card-grid">
        {cards.map((card) => (
          <Link key={card.label} to={card.to} className="stat-card stat-card-link">
            <p className="stat-value">{card.value}</p>
            <p className="stat-label">{card.label}</p>
          </Link>
        ))}
      </div>

      <div className="info-banner">{t("dashboard.sprintNote")}</div>
    </section>
  );
}
