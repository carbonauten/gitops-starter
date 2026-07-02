import { useTranslation } from "react-i18next";

export function PublishPage() {
  const { t } = useTranslation();

  return (
    <section className="page">
      <header className="page-header">
        <h1>{t("publish.title")}</h1>
        <p className="muted">{t("publish.subtitle")}</p>
      </header>
      <div className="empty-state">{t("publish.empty")}</div>
    </section>
  );
}
