import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";

import {
  clearEntraConfig,
  disconnectOutlook,
  fetchEntraConfigStatus,
  fetchOutlookStatus,
  outlookConnectUrl,
  saveEntraConfig,
  type EntraConfigStatus,
  type OutlookStatus,
} from "../api/client";
import { OutlookMailPanel } from "../components/OutlookMailPanel";
import { usePermissions } from "../hooks/usePermissions";

export function OutlookMailPage() {
  const { t } = useTranslation();
  const { isItMaster } = usePermissions();
  const [searchParams, setSearchParams] = useSearchParams();
  const [outlook, setOutlook] = useState<OutlookStatus | null>(null);
  const [entra, setEntra] = useState<EntraConfigStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [tenantId, setTenantId] = useState("");
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");

  useEffect(() => {
    void (async () => {
      try {
        setOutlook(await fetchOutlookStatus());
      } catch {
        setOutlook(null);
      }
      if (isItMaster) {
        try {
          const status = await fetchEntraConfigStatus();
          setEntra(status);
          setTenantId(status.tenant_id || "");
          setClientId(status.client_id || "");
        } catch {
          setEntra(null);
        }
      }
    })();
  }, [reloadKey, isItMaster]);

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

  async function handleSaveEntra(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const status = await saveEntraConfig({
        tenant_id: tenantId.trim(),
        client_id: clientId.trim(),
        client_secret: clientSecret.trim(),
      });
      setEntra(status);
      setClientSecret("");
      setOutlook(await fetchOutlookStatus());
      setNotice(t("mail.entraSaved"));
      setReloadKey((value) => value + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function handleClearEntra() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const status = await clearEntraConfig();
      setEntra(status);
      setTenantId("");
      setClientId("");
      setClientSecret("");
      setOutlook(await fetchOutlookStatus());
      setNotice(t("mail.entraCleared"));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  const oauthReady = Boolean(outlook?.oauth_available);
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

        {oauthReady ? (
          <div className="outlook-connect-actions">
            {outlook?.connected ? (
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
            )}
            {isItMaster && (outlook?.admin_consent_url || entra?.admin_consent_url) ? (
              <div className="entra-admin-consent">
                <p className="muted">{t("mail.adminConsentHint")}</p>
                <a
                  className="ghost-button link-button"
                  href={outlook?.admin_consent_url || entra?.admin_consent_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  {t("mail.adminConsentButton")}
                </a>
              </div>
            ) : null}
          </div>
        ) : isItMaster ? (
          <div className="entra-setup-panel">
            <p className="warning-text">{t("mail.entraSetupNeeded")}</p>
            <ol className="entra-setup-steps">
              <li>{t("mail.entraStepApp")}</li>
              <li>{t("mail.entraStepRedirect")}</li>
              <li>{t("mail.entraStepPerms")}</li>
              <li>{t("mail.entraStepPaste")}</li>
            </ol>
            {(entra?.redirect_uris || []).length > 0 ? (
              <ul className="entra-redirect-list">
                {entra?.redirect_uris.map((uri) => (
                  <li key={uri}>
                    <code>{uri}</code>
                  </li>
                ))}
              </ul>
            ) : null}
            <form className="entra-setup-form" onSubmit={(event) => void handleSaveEntra(event)}>
              <label>
                {t("mail.entraTenant")}
                <input
                  value={tenantId}
                  onChange={(event) => setTenantId(event.target.value)}
                  placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                  required
                  autoComplete="off"
                />
              </label>
              <label>
                {t("mail.entraClientId")}
                <input
                  value={clientId}
                  onChange={(event) => setClientId(event.target.value)}
                  placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                  required
                  autoComplete="off"
                />
              </label>
              <label>
                {t("mail.entraClientSecret")}
                <input
                  type="password"
                  value={clientSecret}
                  onChange={(event) => setClientSecret(event.target.value)}
                  placeholder={entra?.has_client_secret ? t("mail.entraSecretKeep") : ""}
                  required={!entra?.has_client_secret}
                  autoComplete="new-password"
                />
              </label>
              <div className="row-actions">
                <button type="submit" className="primary-button" disabled={busy}>
                  {t("mail.entraSave")}
                </button>
                {entra?.stored_configured ? (
                  <button
                    type="button"
                    className="ghost-button"
                    disabled={busy}
                    onClick={() => void handleClearEntra()}
                  >
                    {t("mail.entraClear")}
                  </button>
                ) : null}
              </div>
            </form>
          </div>
        ) : (
          <p className="muted">{t("mail.entraAskAdmin")}</p>
        )}

        {notice ? <p className="success-text">{notice}</p> : null}
        {error ? <p className="error-text">{error}</p> : null}
      </div>

      <OutlookMailPanel key={reloadKey} connected={connected} />
    </section>
  );
}
