import { FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  clearMailServerConfig,
  createMailbox,
  deleteMailbox,
  fetchMailServerStatus,
  fetchMailboxes,
  saveMailServerConfig,
  type Mailbox,
  type MailServerStatus,
} from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";

export function MailServerPage() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<MailServerStatus | null>(null);
  const [mailboxes, setMailboxes] = useState<Mailbox[]>([]);
  const [domainFilter, setDomainFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const [apiUrl, setApiUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [defaultDomain, setDefaultDomain] = useState("");

  const [newLocalPart, setNewLocalPart] = useState("");
  const [newDomain, setNewDomain] = useState("");
  const [newDisplayName, setNewDisplayName] = useState("");
  const [newPassword, setNewPassword] = useState("");

  async function reload() {
    setLoading(true);
    setError("");
    try {
      const nextStatus = await fetchMailServerStatus();
      setStatus(nextStatus);
      setApiUrl(nextStatus.api_url);
      setDefaultDomain(nextStatus.default_domain);
      if (!newDomain) setNewDomain(nextStatus.default_domain);
      setMailboxes(await fetchMailboxes(domainFilter || nextStatus.default_domain));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSaveConfig(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await saveMailServerConfig({ api_url: apiUrl, api_key: apiKey, default_domain: defaultDomain });
      setApiKey("");
      setNotice(t("mailServer.configSaved"));
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function handleClearConfig() {
    if (!window.confirm(t("mailServer.confirmClearConfig"))) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await clearMailServerConfig();
      setNotice(t("mailServer.configCleared"));
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateMailbox(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const mailbox = await createMailbox({
        local_part: newLocalPart,
        domain: newDomain || defaultDomain,
        display_name: newDisplayName,
        password: newPassword,
      });
      setNotice(t("mailServer.mailboxCreated", { email: mailbox.email }));
      setNewLocalPart("");
      setNewDisplayName("");
      setNewPassword("");
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteMailbox(email: string) {
    if (!window.confirm(t("mailServer.confirmDeleteMailbox", { email }))) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await deleteMailbox(email);
      setNotice(t("mailServer.mailboxDeleted", { email }));
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="page">
      <header className="page-header">
        <h1>{t("mailServer.title")}</h1>
        <p className="muted">{t("mailServer.subtitle")}</p>
      </header>

      {error ? <p className="error-text">{error}</p> : null}
      {notice ? (
        <p className="success-text" role="status">
          {notice}
        </p>
      ) : null}

      <div className="integration-connect-block">
        <div className="integration-connect-header">
          <strong>{t("mailServer.configTitle")}</strong>
          {status ? (
            <span className={status.configured ? "integration-badge integration-badge-connected" : "integration-badge"}>
              {status.mock ? t("mailServer.mockMode") : t("mailServer.liveMode")}
            </span>
          ) : null}
        </div>
        <p className="muted">{t("mailServer.configHint")}</p>
        {status?.mock ? <p className="warning-text">{t("mailServer.mockModeHint")}</p> : null}

        <form className="entra-setup-form" onSubmit={(event) => void handleSaveConfig(event)}>
          <label>
            {t("mailServer.apiUrl")}
            <input
              value={apiUrl}
              onChange={(event) => setApiUrl(event.target.value)}
              placeholder="https://mail.carbonauten.com"
              required
              autoComplete="off"
            />
          </label>
          <label>
            {t("mailServer.apiKey")}
            <input
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder={status?.stored_configured ? t("mailServer.apiKeyKeep") : ""}
              autoComplete="new-password"
            />
          </label>
          <label>
            {t("mailServer.defaultDomain")}
            <input
              value={defaultDomain}
              onChange={(event) => setDefaultDomain(event.target.value)}
              placeholder="carbonauten.com"
              autoComplete="off"
            />
          </label>
          <div className="row-actions">
            <button type="submit" className="primary-button" disabled={busy}>
              {busy ? t("common.loading") : t("mailServer.saveConfig")}
            </button>
            {status?.stored_configured ? (
              <button type="button" className="ghost-button" disabled={busy} onClick={() => void handleClearConfig()}>
                {t("mailServer.clearConfig")}
              </button>
            ) : null}
          </div>
        </form>
      </div>

      <div className="integration-connect-block">
        <div className="integration-connect-header">
          <strong>{t("mailServer.createTitle")}</strong>
        </div>
        <form className="entra-setup-form" onSubmit={(event) => void handleCreateMailbox(event)}>
          <div className="row-actions">
            <label>
              {t("mailServer.localPart")}
              <input
                value={newLocalPart}
                onChange={(event) => setNewLocalPart(event.target.value)}
                placeholder="info"
                required
                autoComplete="off"
              />
            </label>
            <label>
              {t("mailServer.domain")}
              <input
                value={newDomain}
                onChange={(event) => setNewDomain(event.target.value)}
                placeholder="carbonauten.com"
                required
                autoComplete="off"
              />
            </label>
          </div>
          <label>
            {t("mailServer.displayName")}
            <input
              value={newDisplayName}
              onChange={(event) => setNewDisplayName(event.target.value)}
              autoComplete="off"
            />
          </label>
          <label>
            {t("mailServer.password")}
            <input
              type="password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              minLength={8}
              required
              autoComplete="new-password"
            />
          </label>
          <button type="submit" className="primary-button" disabled={busy}>
            {busy ? t("common.loading") : t("mailServer.createMailbox")}
          </button>
        </form>
      </div>

      <div className="toolbar">
        <input
          type="search"
          value={domainFilter}
          onChange={(event) => setDomainFilter(event.target.value)}
          onBlur={() => void reload()}
          placeholder={t("mailServer.filterDomainPlaceholder")}
        />
      </div>

      {loading ? <LoadingState /> : null}
      {!loading && mailboxes.length === 0 ? <EmptyState message={t("mailServer.empty")} icon="✉" /> : null}

      <div className="list-stack">
        {!loading
          ? mailboxes.map((mailbox) => (
              <article key={mailbox.email} className="list-card">
                <div>
                  <h2>{mailbox.email}</h2>
                  <p className="muted">
                    {mailbox.display_name || "—"} · {mailbox.quota_mb} MB
                    {!mailbox.active ? ` · ${t("mailServer.inactive")}` : ""}
                  </p>
                </div>
                <div className="list-card-actions">
                  <button
                    type="button"
                    className="ghost-button danger"
                    disabled={busy}
                    onClick={() => void handleDeleteMailbox(mailbox.email)}
                  >
                    {t("mailServer.delete")}
                  </button>
                </div>
              </article>
            ))
          : null}
      </div>
    </section>
  );
}
