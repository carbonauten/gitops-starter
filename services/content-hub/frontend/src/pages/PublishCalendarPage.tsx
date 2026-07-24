import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { PublishCalendarPanel } from "../components/PublishCalendarPanel";

export function PublishCalendarPage() {
  const { t } = useTranslation();

  return (
    <section className="page">
      <header className="page-header row-header">
        <div>
          <p className="eyebrow">{t("calendar.eyebrow")}</p>
          <h1>{t("calendar.pageTitle")}</h1>
          <p className="muted">{t("calendar.pageSubtitle")}</p>
        </div>
        <Link to="/publish" className="ghost-button link-button">
          {t("calendar.openPublish")}
        </Link>
      </header>
      <PublishCalendarPanel />
    </section>
  );
}
