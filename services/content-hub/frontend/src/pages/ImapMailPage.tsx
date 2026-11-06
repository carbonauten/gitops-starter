import { FormEvent, useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  createImapAccount,
  deleteImapAccount,
  fetchAiStatus,
  fetchImapAccounts,
  fetchImapMessage,
  fetchImapMessages,
  summarizeImapMessage,
  type ImapAccount,
  type ImapMailMessage,
  type ImapMailSummary,
} from "../api/client";
import { EmailBodyFrame } from "../components/EmailBodyFrame";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";

export function ImapMailPage() {
  const { t, i18n } = useTranslation();
  const [accounts, setAccounts] = useState<ImapAccount[]>([]);
  const [loadingAccounts, setLoadingAccounts] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [label, setLabel] = useState("");
  const [host, setHost] = useState("");
  const [port, setPort] = useState("993");
  const [useSsl, setUseSsl] = useState(true);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [folder, setFolder] = useState("INBOX");

  const [selectedAccountId, setSelectedAccountId] = useState("");
  const [messages, setMessages] = useState<ImapMailSummary[]>([]);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [selectedMessageId, setSelectedMessageId] = useState("");
  const [detail, setDetail] = useState<ImapMailMessage | null>(null);
  const [mailError, setMailError] = useState("");

  const [aiAvailable, setAiAvailable] = useState(false);
  const [summarizing, setSummarizing] = useState(false);
  const [summary, setSummary] = useState("");
  const [summaryError, setSummaryError] = useState("");

  async function reloadAccounts() {
    setLoadingAccounts(true);
    setError("");
    try {
      const list = await fetchImapAccounts();
      setAccounts(list);
      if (!selectedAccountId && list.length > 0) {
        setSelectedAccountId(list[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setLoadingAccounts(false);
    }
  }

  useEffect(() => {
    void reloadAccounts();
    void (async () => {
      try {
        setAiAvailable((await fetchAiStatus()).available);
      } catch {
        setAiAvailable(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadMessages = useCallback(
    async (accountId: string) => {
      if (!accountId) {
        setMessages([]);
        return;
      }
      setLoadingMessages(true);
      setMailError("");
      try {
        setMessages(await fetchImapMessages(accountId, 30));
      } catch (err) {
        setMailError(err instanceof Error ? err.message : t("common.error"));
        setMessages([]);
      } finally {
        setLoadingMessages(false);
      }
    },
    [t],
  );

  useEffect(() => {
    setSelectedMessageId("");
    setDetail(null);
    setSummary("");
    setSummaryError("");
    void loadMessages(selectedAccountId);
  }, [selectedAccountId, loadMessages]);

  async function handleCreateAccount(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const account = await createImapAccount({
        label,
        host,
        port: Number(port) || 993,
        use_ssl: useSsl,
        username,
        password,
        folder,
      });
      setNotice(t("imapMail.accountCreated", { label: account.label }));
      setLabel("");
      setHost("");
      setPort("993");
      setUseSsl(true);
      setUsername("");
      setPassword("");
      setFolder("INBOX");
      await reloadAccounts();
      setSelectedAccountId(account.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteAccount(accountId: string, accountLabel: string) {
    if (!window.confirm(t("imapMail.confirmDeleteAccount", { label: accountLabel }))) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await deleteImapAccount(accountId);
      setNotice(t("imapMail.accountDeleted", { label: accountLabel }));
      if (selectedAccountId === accountId) {
        setSelectedAccountId("");
        setMessages([]);
        setDetail(null);
      }
      await reloadAccounts();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function handleSelectMessage(messageId: string) {
    setSelectedMessageId(messageId);
    setDetail(null);
    setMailError("");
    setSummary("");
    setSummaryError("");
    try {
      setDetail(await fetchImapMessage(selectedAccountId, messageId));
    } catch (err) {
      setMailError(err instanceof Error ? err.message : t("common.error"));
    }
  }

  async function handleSummarize() {
    if (!selectedAccountId || !selectedMessageId) return;
    setSummarizing(true);
    setSummaryError("");
    try {
      const uiLanguage = (["de", "en", "zh-CN"].includes(i18n.language) ? i18n.language : "de") as
        | "de"
        | "en"
        | "zh-CN";
      setSummary(await summarizeImapMessage(selectedAccountId, selectedMessageId, uiLanguage));
    } catch (err) {
      setSummaryError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setSummarizing(false);
    }
  }

  return (
    <section className="page">
      <header className="page-header">
        <h1>{t("imapMail.title")}</h1>
        <p className="muted">{t("imapMail.subtitle")}</p>
      </header>

      {error ? <p className="error-text">{error}</p> : null}
      {notice ? (
        <p className="success-text" role="status">
          {notice}
        </p>
      ) : null}

      <div className="integration-connect-block">
        <div className="integration-connect-header">
          <strong>{t("imapMail.createTitle")}</strong>
        </div>
        <p className="muted">{t("imapMail.createHint")}</p>
        <form className="entra-setup-form" onSubmit={(event) => void handleCreateAccount(event)}>
          <label>
            {t("imapMail.label")}
            <input
              value={label}
              onChange={(event) => setLabel(event.target.value)}
              placeholder="info@carbonauten.com"
              required
              autoComplete="off"
            />
          </label>
          <div className="row-actions">
            <label>
              {t("imapMail.host")}
              <input
                value={host}
                onChange={(event) => setHost(event.target.value)}
                placeholder="imap.strato.de"
                required
                autoComplete="off"
              />
            </label>
            <label>
              {t("imapMail.port")}
              <input
                type="number"
                value={port}
                onChange={(event) => setPort(event.target.value)}
                min={1}
                max={65535}
                required
              />
            </label>
          </div>
          <label className="checkbox-row">
            <input type="checkbox" checked={useSsl} onChange={(event) => setUseSsl(event.target.checked)} />
            {t("imapMail.useSsl")}
          </label>
          <label>
            {t("imapMail.username")}
            <input
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="info@carbonauten.com"
              required
              autoComplete="off"
            />
          </label>
          <label>
            {t("imapMail.password")}
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              autoComplete="new-password"
            />
          </label>
          <label>
            {t("imapMail.folder")}
            <input value={folder} onChange={(event) => setFolder(event.target.value)} placeholder="INBOX" />
          </label>
          <button type="submit" className="primary-button" disabled={busy}>
            {busy ? t("common.loading") : t("imapMail.createAccount")}
          </button>
        </form>
      </div>

      {loadingAccounts ? <LoadingState /> : null}
      {!loadingAccounts && accounts.length === 0 ? (
        <EmptyState message={t("imapMail.empty")} icon="✉" />
      ) : null}

      {!loadingAccounts && accounts.length > 0 ? (
        <>
          <div className="toolbar">
            <label>
              {t("imapMail.selectAccount")}
              <select value={selectedAccountId} onChange={(event) => setSelectedAccountId(event.target.value)}>
                {accounts.map((account) => (
                  <option key={account.id} value={account.id}>
                    {account.label} ({account.username})
                  </option>
                ))}
              </select>
            </label>
            {selectedAccountId ? (
              <button
                type="button"
                className="ghost-button danger"
                disabled={busy}
                onClick={() => {
                  const account = accounts.find((entry) => entry.id === selectedAccountId);
                  if (account) void handleDeleteAccount(account.id, account.label);
                }}
              >
                {t("imapMail.deleteAccount")}
              </button>
            ) : null}
          </div>

          <section className="outlook-mail-panel">
            {mailError ? <p className="error-text">{mailError}</p> : null}
            <div className="outlook-mail-layout">
              <div className="outlook-mail-list-pane">
                {loadingMessages ? <p className="muted">{t("common.loading")}</p> : null}
                {!loadingMessages && messages.length === 0 ? (
                  <p className="muted">{t("imapMail.noMessages")}</p>
                ) : null}
                <ul className="outlook-mail-list">
                  {messages.map((message) => (
                    <li key={message.id}>
                      <button
                        type="button"
                        className={`outlook-mail-item${selectedMessageId === message.id ? " is-selected" : ""}${
                          message.is_read ? "" : " is-unread"
                        }`}
                        onClick={() => void handleSelectMessage(message.id)}
                      >
                        <span className="outlook-mail-item-subject">{message.subject}</span>
                        <span className="outlook-mail-item-from">
                          {message.from.name || message.from.email || "—"}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="outlook-mail-detail-pane">
                {!detail ? (
                  <p className="muted">{t("imapMail.selectHint")}</p>
                ) : (
                  <>
                    <div className="outlook-mail-detail-actions">
                      {aiAvailable ? (
                        <button
                          type="button"
                          className="ghost-button"
                          disabled={summarizing}
                          onClick={() => void handleSummarize()}
                        >
                          {summarizing ? t("common.loading") : t("mail.aiSummarize")}
                        </button>
                      ) : null}
                    </div>
                    <h3>{detail.subject}</h3>
                    <p className="muted">
                      {t("mail.from")}: {detail.from.name || detail.from.email || "—"}
                      {detail.from.name && detail.from.email ? ` <${detail.from.email}>` : ""}
                    </p>
                    <p className="muted">
                      {t("mail.received")}: {detail.received_at || "—"}
                    </p>
                    {summaryError ? <p className="error-text">{summaryError}</p> : null}
                    {summary ? (
                      <div className="ai-summary-box">
                        <strong>{t("mail.aiSummaryTitle")}</strong>
                        <pre>{summary}</pre>
                      </div>
                    ) : null}
                    <EmailBodyFrame body={detail.body} bodyType={detail.body_type} />
                  </>
                )}
              </div>
            </div>
          </section>
        </>
      ) : null}
    </section>
  );
}
