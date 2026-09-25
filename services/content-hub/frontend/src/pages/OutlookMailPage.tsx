import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";

import {
  disconnectOutlook,
  fetchOutlookStatus,
  outlookConnectUrl,
  type OutlookStatus,
} from "../api/client";
import { OutlookMailPanel } from "../components/OutlookMailPanel";

export function OutlookMailPage() {
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
      setNotice(t("mail.outlookConnected"));
      setReloadKey((value) => value + 1);
    } else if (status === "error") {
      setError(t("mail.outlookFailed"));
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
      setNotice(t("mail.outlookDisconnected"));
      setReloadKey((value) => value + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  const connected = Boolean(outlook?.connected && outlook?.mail_enabled !== false);

  return (
    <section className="page">
      <header className="page-header row-header">
        <div>
          <p className="eyebrow">{t("mail.eyebrow")}</p>
          <h1>{t("mail.pageTitle")}</h1>
          <p className="muted">{t("mail.pageSubtitle")}</p>
        </div>
        <Link to="/files" className="ghost-button link-button">
          {t("mail.openFiles")}
        </Link>
      </header>

      <div className="integration-connect-block outlook-connect-card">
        <div className="integration-connect-header">
          <strong>{t("mail.outlookTitle")}</strong>
          {outlook?.connected ? (
            <span className="integration-badge integration-badge-connected">
              {outlook.account || t("mail.connected")}
            </span>
          ) : (
            <span className="integration-badge">{t("mail.notConnected")}</span>
          )}
        </div>
        <p className="muted">{t("mail.outlookHint")}</p>
        {outlook?.oauth_available ? (
          outlook.connected ? (
            <button
              type="button"
              className="ghost-button"
              disabled={busy}
              onClick={() => void handleDisconnect()}
            >
              {t("mail.outlookDisconnect")}
            </button>
          ) : (
            <a className="primary-button integration-connect-button" href={outlookConnectUrl()}>
              {t("mail.outlookConnect")}
            </a>
          )
        ) : (
          <p className="muted">{t("mail.outlookEnvMissing")}</p>
        )}
        {notice ? <p className="success-text">{notice}</p> : null}
        {error ? <p className="error-text">{error}</p> : null}
      </div>

      <OutlookMailPanel key={reloadKey} connected={connected} />
    </section>
  );
}
