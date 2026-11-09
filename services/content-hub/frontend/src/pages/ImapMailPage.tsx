import { FormEvent, useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  clearStratoAutomationConfig,
  createImapAccount,
  createStratoMailboxAutomated,
  deleteImapAccount,
  fetchAiStatus,
  fetchImapAccounts,
  fetchImapMessage,
  fetchImapMessages,
  fetchStratoAutomationStatus,
  saveStratoAutomationConfig,
  StratoAutomationApiError,
  summarizeImapMessage,
  updateImapAccount,
  type ImapAccount,
  type ImapMailMessage,
  type ImapMailSummary,
  type StratoAutomationStatus,
} from "../api/client";
import { EmailBodyFrame } from "../components/EmailBodyFrame";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";

function formatDateTime(iso: string | null | undefined, locale: string): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function generatePassword(length = 16): string {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789!@#%^*";
  const bytes = new Uint8Array(length);
  window.crypto.getRandomValues(bytes);
  return Array.from(bytes, (value) => chars[value % chars.length]).join("");
}

export function ImapMailPage() {
  const { t, i18n } = useTranslation();
  const [accounts, setAccounts] = useState<ImapAccount[]>([]);
  const [loadingAccounts, setLoadingAccounts] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showAccountPanel, setShowAccountPanel] = useState(false);
  const [editingAccountId, setEditingAccountId] = useState<string | null>(null);

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
  const [query, setQuery] = useState("");
  const [selectedMessageId, setSelectedMessageId] = useState("");
  const [detail, setDetail] = useState<ImapMailMessage | null>(null);
  const [mailError, setMailError] = useState("");

  const [aiAvailable, setAiAvailable] = useState(false);
  const [summarizing, setSummarizing] = useState(false);
  const [summary, setSummary] = useState("");
  const [summaryError, setSummaryError] = useState("");

  const [stratoStatus, setStratoStatus] = useState<StratoAutomationStatus | null>(null);
  const [stratoBusy, setStratoBusy] = useState(false);
  const [stratoCustomerNumber, setStratoCustomerNumber] = useState("");
  const [stratoPassword, setStratoPassword] = useState("");
  const [autoLocalPart, setAutoLocalPart] = useState("");
  const [autoDomain, setAutoDomain] = useState("");
  const [autoPassword, setAutoPassword] = useState("");
  const [autoCreating, setAutoCreating] = useState(false);
  const [autoError, setAutoError] = useState("");
  const [autoScreenshot, setAutoScreenshot] = useState<string | null>(null);
  const [autoNotice, setAutoNotice] = useState("");

  async function reloadAccounts() {
    setLoadingAccounts(true);
    setError("");
    try {
      const list = await fetchImapAccounts();
      setAccounts(list);
      if (list.length === 0) {
        setShowAccountPanel(true);
      }
      if (!selectedAccountId && list.length > 0) {
        setSelectedAccountId(list[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setLoadingAccounts(false);
    }
  }

  async function reloadStratoStatus() {
    try {
      setStratoStatus(await fetchStratoAutomationStatus());
    } catch {
      setStratoStatus(null);
    }
  }

  useEffect(() => {
    void reloadAccounts();
    void reloadStratoStatus();
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
    async (accountId: string, search = "") => {
      if (!accountId) {
        setMessages([]);
        return;
      }
      setLoadingMessages(true);
      setMailError("");
      try {
        setMessages(await fetchImapMessages(accountId, { top: 30, q: search }));
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
    setQuery("");
    void loadMessages(selectedAccountId);
  }, [selectedAccountId, loadMessages]);

  async function handleCreateAccount(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const account = editingAccountId
        ? await updateImapAccount(editingAccountId, {
            label,
            host,
            port: Number(port) || 993,
            use_ssl: useSsl,
            username,
            password,
            folder,
          })
        : await createImapAccount({
            label,
            host,
            port: Number(port) || 993,
            use_ssl: useSsl,
            username,
            password,
            folder,
          });
      setNotice(
        editingAccountId
          ? t("imapMail.accountUpdated", { label: account.label })
          : t("imapMail.accountCreated", { label: account.label }),
      );
      setEditingAccountId(null);
      setLabel("");
      setHost("");
      setPort("993");
      setUseSsl(true);
      setUsername("");
      setPassword("");
      setFolder("INBOX");
      await reloadAccounts();
      setSelectedAccountId(account.id);
      setShowAccountPanel(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  function handleEditAccount(account: ImapAccount) {
    setEditingAccountId(account.id);
    setLabel(account.label);
    setHost(account.host);
    setPort(String(account.port));
    setUseSsl(account.use_ssl);
    setUsername(account.username);
    setPassword("");
    setFolder(account.folder);
    setError("");
    setNotice("");
  }

  function handleCancelEdit() {
    setEditingAccountId(null);
    setLabel("");
    setHost("");
    setPort("993");
    setUseSsl(true);
    setUsername("");
    setPassword("");
    setFolder("INBOX");
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
      if (editingAccountId === accountId) {
        handleCancelEdit();
      }
      await reloadAccounts();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveStratoConfig(event: FormEvent) {
    event.preventDefault();
    setStratoBusy(true);
    setError("");
    setNotice("");
    try {
      await saveStratoAutomationConfig({ customer_number: stratoCustomerNumber, password: stratoPassword });
      setStratoPassword("");
      setNotice(t("imapMail.autoConfigSaved"));
      await reloadStratoStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setStratoBusy(false);
    }
  }

  async function handleClearStratoConfig() {
    if (!window.confirm(t("imapMail.autoConfirmClearConfig"))) return;
    setStratoBusy(true);
    setError("");
    setNotice("");
    try {
      await clearStratoAutomationConfig();
      setStratoCustomerNumber("");
      setNotice(t("imapMail.autoConfigCleared"));
      await reloadStratoStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setStratoBusy(false);
    }
  }

  async function handleAutomatedCreate(event: FormEvent) {
    event.preventDefault();
    setAutoCreating(true);
    setAutoError("");
    setAutoScreenshot(null);
    setAutoNotice("");
    try {
      const result = await createStratoMailboxAutomated({
        local_part: autoLocalPart,
        domain: autoDomain,
        password: autoPassword,
      });
      // Automation only creates the mailbox at Strato - immediately connect
      // it here too with the same credentials so it's usable right away.
      // This second step can fail independently of the first (e.g. a
      // brand-new mailbox not yet reachable over IMAP for a minute or two),
      // so it gets its own try/catch: a failure here must say the mailbox
      // already exists at Strato, not look like the whole thing failed -
      // otherwise the obvious next move (retrying "Automatisch anlegen")
      // would hit Strato with an address that's already taken.
      try {
        await createImapAccount({
          label: result.email,
          host: "imap.strato.de",
          port: 993,
          use_ssl: true,
          username: result.email,
          password: autoPassword,
          folder: "INBOX",
        });
        setAutoNotice(t("imapMail.autoCreateSuccess", { email: result.email }));
        setAutoLocalPart("");
        setAutoDomain("");
        setAutoPassword("");
        await reloadAccounts();
      } catch (connectErr) {
        setAutoError(
          t("imapMail.autoCreatedButConnectFailed", {
            email: result.email,
            error: connectErr instanceof Error ? connectErr.message : t("common.error"),
          }),
        );
        setLabel(result.email);
        setUsername(result.email);
        setPassword(autoPassword);
      }
    } catch (err) {
      if (err instanceof StratoAutomationApiError) {
        setAutoError(err.message);
        setAutoScreenshot(err.screenshotBase64);
      } else {
        setAutoError(err instanceof Error ? err.message : t("common.error"));
      }
    } finally {
      setAutoCreating(false);
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

  const unreadCount = messages.filter((message) => !message.is_read).length;

  return (
    <section className="page">
      <header className="page-header row-header">
        <div>
          <h1>{t("imapMail.title")}</h1>
          <p className="muted">{t("imapMail.subtitle")}</p>
        </div>
        <button type="button" className="ghost-button" onClick={() => setShowAccountPanel((value) => !value)}>
          {showAccountPanel ? t("imapMail.hideAccounts") : t("imapMail.manageAccounts")}
        </button>
      </header>

      {error ? <p className="error-text">{error}</p> : null}
      {notice ? (
        <p className="success-text" role="status">
          {notice}
        </p>
      ) : null}

      {loadingAccounts ? <LoadingState /> : null}

      {!loadingAccounts && showAccountPanel ? (
        <>
          {accounts.length > 0 ? (
            <div className="integration-connect-block">
              <div className="integration-connect-header">
                <strong>{t("imapMail.connectedAccounts")}</strong>
              </div>
              <div className="list-stack">
                {accounts.map((account) => (
                  <article key={account.id} className="list-card">
                    <div>
                      <h2>{account.label}</h2>
                      <p className="muted">
                        {account.username} · {account.host}:{account.port} · {account.folder}
                      </p>
                    </div>
                    <div className="list-card-actions">
                      <button type="button" className="ghost-button" disabled={busy} onClick={() => handleEditAccount(account)}>
                        {t("imapMail.editAccount")}
                      </button>
                      <button
                        type="button"
                        className="ghost-button danger"
                        disabled={busy}
                        onClick={() => void handleDeleteAccount(account.id, account.label)}
                      >
                        {t("imapMail.deleteAccount")}
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            </div>
          ) : null}

          <div className="integration-connect-block">
            <div className="integration-connect-header">
              <strong>{t("imapMail.newMailboxTitle")}</strong>
            </div>
            <p className="muted">{t("imapMail.newMailboxHint")}</p>
            <a
              className="ghost-button link-button"
              href="https://www.strato.de/login"
              target="_blank"
              rel="noreferrer"
            >
              {t("imapMail.openStrato")}
            </a>
          </div>

          <div className="integration-connect-block">
            <div className="integration-connect-header">
              <strong>{t("imapMail.autoTitle")}</strong>
              {stratoStatus ? (
                <span
                  className={
                    stratoStatus.configured ? "integration-badge integration-badge-connected" : "integration-badge"
                  }
                >
                  {stratoStatus.configured ? t("imapMail.autoConfigured") : t("imapMail.autoNotConfigured")}
                </span>
              ) : null}
            </div>
            <p className="warning-text">{t("imapMail.autoWarning")}</p>
            <p className="muted">{t("imapMail.autoHint")}</p>

            {!stratoStatus?.configured ? (
              <form className="entra-setup-form" onSubmit={(event) => void handleSaveStratoConfig(event)}>
                <label>
                  {t("imapMail.autoCustomerNumber")}
                  <input
                    value={stratoCustomerNumber}
                    onChange={(event) => setStratoCustomerNumber(event.target.value)}
                    required
                    autoComplete="off"
                  />
                </label>
                <label>
                  {t("imapMail.autoCustomerPassword")}
                  <input
                    type="password"
                    value={stratoPassword}
                    onChange={(event) => setStratoPassword(event.target.value)}
                    required
                    autoComplete="new-password"
                  />
                </label>
                <button type="submit" className="primary-button" disabled={stratoBusy}>
                  {stratoBusy ? t("common.loading") : t("imapMail.autoSaveConfig")}
                </button>
              </form>
            ) : (
              <>
                <div className="row-actions">
                  <span className="muted">
                    {t("imapMail.autoConfiguredAs", { number: stratoStatus.customer_number })}
                  </span>
                  <button
                    type="button"
                    className="ghost-button danger"
                    disabled={stratoBusy}
                    onClick={() => void handleClearStratoConfig()}
                  >
                    {t("imapMail.autoClearConfig")}
                  </button>
                </div>

                <form className="entra-setup-form" onSubmit={(event) => void handleAutomatedCreate(event)}>
                  <div className="row-actions">
                    <label>
                      {t("imapMail.label")}
                      <input
                        value={autoLocalPart}
                        onChange={(event) => setAutoLocalPart(event.target.value)}
                        placeholder="sales"
                        required
                        autoComplete="off"
                      />
                    </label>
                    <label>
                      {t("imapMail.domain")}
                      <input
                        value={autoDomain}
                        onChange={(event) => setAutoDomain(event.target.value)}
                        placeholder="carbonauten.com"
                        required
                        autoComplete="off"
                      />
                    </label>
                  </div>
                  <label>
                    {t("imapMail.password")}
                    <div className="row-actions">
                      <input
                        type="text"
                        value={autoPassword}
                        onChange={(event) => setAutoPassword(event.target.value)}
                        minLength={8}
                        required
                        autoComplete="off"
                      />
                      <button type="button" className="ghost-button" onClick={() => setAutoPassword(generatePassword())}>
                        {t("imapMail.autoGeneratePassword")}
                      </button>
                    </div>
                  </label>
                  <button type="submit" className="primary-button" disabled={autoCreating}>
                    {autoCreating ? t("imapMail.autoCreating") : t("imapMail.autoCreateButton")}
                  </button>
                </form>
              </>
            )}

            {autoNotice ? <p className="success-text">{autoNotice}</p> : null}
            {autoError ? (
              <div>
                <p className="error-text">{autoError}</p>
                {autoScreenshot ? (
                  <details>
                    <summary>{t("imapMail.autoScreenshotLabel")}</summary>
                    <img
                      src={`data:image/png;base64,${autoScreenshot}`}
                      alt=""
                      style={{ maxWidth: "100%", border: "1px solid var(--border, #e4e7ec)", borderRadius: 8 }}
                    />
                  </details>
                ) : null}
              </div>
            ) : null}
          </div>

          <div className="integration-connect-block">
            <div className="integration-connect-header">
              <strong>{editingAccountId ? t("imapMail.editTitle") : t("imapMail.createTitle")}</strong>
            </div>
            <p className="muted">{editingAccountId ? t("imapMail.editHint") : t("imapMail.createHint")}</p>
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
                  placeholder={editingAccountId ? t("imapMail.passwordKeep") : ""}
                  required={!editingAccountId}
                  autoComplete="new-password"
                />
              </label>
              <label>
                {t("imapMail.folder")}
                <input value={folder} onChange={(event) => setFolder(event.target.value)} placeholder="INBOX" />
              </label>
              <p className="muted">{t("imapMail.testHint")}</p>
              <div className="row-actions">
                <button type="submit" className="primary-button" disabled={busy}>
                  {busy
                    ? t("imapMail.testing")
                    : editingAccountId
                      ? t("imapMail.saveAccount")
                      : t("imapMail.createAccount")}
                </button>
                {editingAccountId ? (
                  <button type="button" className="ghost-button" disabled={busy} onClick={handleCancelEdit}>
                    {t("imapMail.cancelEdit")}
                  </button>
                ) : null}
              </div>
            </form>
          </div>
        </>
      ) : null}

      {!loadingAccounts && accounts.length === 0 && !showAccountPanel ? (
        <EmptyState message={t("imapMail.empty")} icon="✉" />
      ) : null}

      {!loadingAccounts && accounts.length > 0 ? (
        <section className="outlook-mail-panel">
          <header className="outlook-mail-header">
            <div>
              <h2>
                {t("imapMail.inboxTitle")}
                {unreadCount > 0 ? (
                  <span className="integration-badge" style={{ marginLeft: "0.5rem" }}>
                    {t("imapMail.unreadCount", { count: unreadCount })}
                  </span>
                ) : null}
              </h2>
              <label style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                {t("imapMail.selectAccount")}
                <select value={selectedAccountId} onChange={(event) => setSelectedAccountId(event.target.value)}>
                  {accounts.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.label} ({account.username})
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <form
              className="outlook-mail-search"
              onSubmit={(event) => {
                event.preventDefault();
                void loadMessages(selectedAccountId, query);
              }}
            >
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={t("imapMail.searchPlaceholder")}
                aria-label={t("imapMail.searchPlaceholder")}
              />
              <button type="submit" className="ghost-button" disabled={loadingMessages}>
                {t("mail.search")}
              </button>
              <button
                type="button"
                className="ghost-button"
                disabled={loadingMessages}
                title={t("imapMail.refresh")}
                onClick={() => void loadMessages(selectedAccountId, query)}
              >
                ⟳
              </button>
            </form>
          </header>

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
                      <span className="outlook-mail-item-subject">
                        {message.subject}
                        {message.has_attachments ? (
                          <span className="imap-attachment-icon" title={t("imapMail.hasAttachments")}>
                            📎
                          </span>
                        ) : null}
                      </span>
                      <span className="outlook-mail-item-from">
                        {message.from.name || message.from.email || "—"}
                        {message.received_at ? ` · ${formatDateTime(message.received_at, i18n.language)}` : ""}
                      </span>
                      {message.preview ? (
                        <span className="outlook-mail-item-preview muted">{message.preview}</span>
                      ) : null}
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
                    {t("mail.received")}: {formatDateTime(detail.received_at, i18n.language)}
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
      ) : null}
    </section>
  );
}
