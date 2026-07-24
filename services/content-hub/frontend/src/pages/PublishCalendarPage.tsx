import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";

import {
  disconnectOutlook,
  fetchOutlookStatus,
  outlookConnectUrl,
  type OutlookStatus,
} from "../api/client";
import { PublishCalendarPanel } from "../components/PublishCalendarPanel";

export function PublishCalendarPage() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [outlook, setOutlook] = useState<OutlookStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    void (async () => {
      try {
        setOutlook(await fetchOutlookStatus());
      } catch {
        setOutlook(null);
      }
    })();
  }, [reloadKey]);

  useEffect(() => {
    const status = searchParams.get("outlook");
    if (!status) return;
    if (status === "success") {
      setNotice(t("calendar.outlookConnected"));
      setReloadKey((value) => value + 1);
    } else if (status === "error") {
      setError(t("calendar.outlookFailed"));
    }
    const next = new URLSearchParams(searchParams);
    next.delete("outlook");
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams, t]);

  async function handleDisconnect() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await disconnectOutlook();
      setOutlook(await fetchOutlookStatus());
      setNotice(t("calendar.outlookDisconnected"));
      setReloadKey((value) => value + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  }

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

      <div className="integration-connect-block outlook-connect-card">
        <div className="integration-connect-header">
          <strong>{t("calendar.outlookTitle")}</strong>
          {outlook?.connected ? (
            <span className="integration-badge integration-badge-connected">
              {outlook.account || t("calendar.connected")}
            </span>
          ) : (
            <span className="integration-badge">{t("calendar.notConnected")}</span>
          )}
        </div>
        <p className="muted">{t("calendar.outlookHint")}</p>
        <ul className="outlook-feature-list">
          <li>{t("calendar.outlookFeatureCalendar")}</li>
          <li>{t("calendar.outlookFeatureMail")}</li>
        </ul>
        {outlook?.oauth_available ? (
          outlook.connected ? (
            <button
              type="button"
              className="ghost-button"
              disabled={busy}
              onClick={() => void handleDisconnect()}
            >
              {t("calendar.outlookDisconnect")}
            </button>
          ) : (
            <a className="primary-button integration-connect-button" href={outlookConnectUrl()}>
              {t("calendar.outlookConnect")}
            </a>
          )
        ) : (
          <p className="muted">{t("calendar.outlookEnvMissing")}</p>
        )}
        {notice ? <p className="success-text">{notice}</p> : null}
        {error ? <p className="error-text">{error}</p> : null}
      </div>

      <PublishCalendarPanel key={reloadKey} />
    </section>
  );
}
