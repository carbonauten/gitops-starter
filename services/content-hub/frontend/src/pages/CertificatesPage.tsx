import { useTranslation } from "react-i18next";

export function CertificatesPage() {
  const { t } = useTranslation();

  const categories = [
    t("certificates.categories.compliance"),
    t("certificates.categories.product"),
    t("certificates.categories.training"),
    t("certificates.categories.ssl"),
  ];

  return (
    <section className="page">
      <header className="page-header">
        <h1>{t("certificates.title")}</h1>
        <p className="muted">{t("certificates.subtitle")}</p>
      </header>

      <div className="card-grid">
        {categories.map((category) => (
          <article key={category} className="stat-card">
            <p className="stat-label">{category}</p>
            <p className="stat-value">0</p>
            <p className="badge">{t("certificates.comingSoon")}</p>
          </article>
        ))}
      </div>

      <div className="info-banner">{t("certificates.empty")}</div>
    </section>
  );
}
