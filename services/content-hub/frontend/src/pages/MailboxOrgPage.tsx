import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  connectMailboxOrg,
  disconnectMailboxOrg,
  fetchMailboxOrgMail,
  fetchMailboxOrgMailMessage,
  fetchMailboxOrgStatus,
  mailboxOrgAttachmentUrl,
  type MailboxOrgMessage,
  type MailboxOrgMessageSummary,
  type MailboxOrgStatus,
} from "../api/client";
import { EmailBodyFrame } from "../components/EmailBodyFrame";

export function MailboxOrgPage() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<MailboxOrgStatus | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [messages, setMessages] = useState<MailboxOrgMessageSummary[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [detail, setDetail] = useState<MailboxOrgMessage | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);

  const loadStatus = useCallback(async () => {
    try {
      setStatus(await fetchMailboxOrgStatus());
    } catch {
      setStatus(null);
    }
  }, []);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  const loadMessages = useCallback(
    async (search = "") => {
      if (!status?.connected) return;
      setLoading(true);
      setError("");
      try {
        const items = await fetchMailboxOrgMail({ q: search, top: 30 });
        setMessages(items);
      } catch (err) {
        setError(err instanceof Error ? err.message : t("common.error"));
      } finally {
        setLoading(false);
      }
    },
    [status?.connected, t],
  );

  useEffect(() => {
    void loadMessages("");
  }, [loadMessages]);

  async function handleConnect(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await connectMailboxOrg(email.trim(), password);
      setStatus(result);
      setPassword("");
      setNotice(t("mailboxOrg.connected"));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function handleDisconnect() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await disconnectMailboxOrg();
      await loadStatus();
      setMessages([]);
      setDetail(null);
      setNotice(t("mailboxOrg.disconnected"));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function handleSelect(id: string) {
    setSelectedId(id);
    setDetail(null);
    setError("");
    try {
      setDetail(await fetchMailboxOrgMailMessage(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    }
  }

  return (
    <section className="page">
      <header className="page-header row-header">
        <div>
          <p className="eyebrow">{t("mailboxOrg.eyebrow")}</p>
          <h1>{t("mailboxOrg.pageTitle")}</h1>
          <p className="muted">{t("mailboxOrg.pageSubtitle")}</p>
        </div>
      </header>

      <div className="integration-connect-block">
        <div className="integration-connect-header">
          <strong>{t("mailboxOrg.title")}</strong>
          {status?.connected ? (
            <span className="integration-badge integration-badge-connected">
              {status.account || t("mail.connected")}
            </span>
          ) : (
            <span className="integration-badge">{t("mail.notConnected")}</span>
          )}
        </div>
        <p className="muted">{t("mailboxOrg.hint")}</p>

        {status?.connected ? (
          <button type="button" className="ghost-button" disabled={busy} onClick={() => void handleDisconnect()}>
            {t("mailboxOrg.disconnect")}
          </button>
        ) : (
          <form className="entra-setup-form" onSubmit={(event) => void handleConnect(event)}>
            <label>
              {t("mailboxOrg.emailLabel")}
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="name@mailbox.org"
                required
                autoComplete="username"
              />
            </label>
            <label>
              {t("mailboxOrg.passwordLabel")}
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
                autoComplete="current-password"
              />
              <span className="muted">{t("mailboxOrg.passwordHint")}</span>
            </label>
            <button type="submit" className="primary-button" disabled={busy}>
              {t("mailboxOrg.connect")}
            </button>
          </form>
        )}

        {notice ? <p className="success-text">{notice}</p> : null}
        {error ? <p className="error-text">{error}</p> : null}
      </div>

      {status?.connected ? (
        <section className="outlook-mail-panel">
          <header className="outlook-mail-header">
            <div>
              <h2>{t("mail.inboxTitle")}</h2>
            </div>
            <form
              className="outlook-mail-search"
              onSubmit={(event) => {
                event.preventDefault();
                void loadMessages(query);
              }}
            >
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={t("mail.searchPlaceholder")}
                aria-label={t("mail.searchPlaceholder")}
              />
              <button type="submit" className="ghost-button" disabled={loading}>
                {t("mail.search")}
              </button>
            </form>
          </header>

          <div className="outlook-mail-layout">
            <div className="outlook-mail-list-pane">
              {loading ? <p className="muted">{t("common.loading")}</p> : null}
              {!loading && messages.length === 0 ? <p className="muted">{t("mail.empty")}</p> : null}
              <ul className="outlook-mail-list">
                {messages.map((message) => (
                  <li key={message.id}>
                    <button
                      type="button"
                      className={`outlook-mail-item${selectedId === message.id ? " is-selected" : ""}${
                        message.is_read ? "" : " is-unread"
                      }`}
                      onClick={() => void handleSelect(message.id)}
                    >
                      <span className="outlook-mail-item-subject">{message.subject}</span>
                      <span className="outlook-mail-item-from">
                        {message.from.name || message.from.email || "—"}
                      </span>
                      <span className="outlook-mail-item-preview muted">{message.preview}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>

            <div className="outlook-mail-detail-pane">
              {!detail ? (
                <p className="muted">{t("mail.selectHint")}</p>
              ) : (
                <>
                  <h3>{detail.subject}</h3>
                  <p className="muted">
                    {t("mail.from")}: {detail.from.name || detail.from.email || "—"}
                  </p>
                  <p className="muted">
                    {t("mail.received")}: {detail.received_at || "—"}
                  </p>
                  {detail.attachments.length > 0 ? (
                    <ul className="meeting-list">
                      {detail.attachments.map((attachment) => (
                        <li key={attachment.index} className="meeting-list-item">
                          <span>{attachment.filename}</span>
                          <a
                            className="ghost-button link-button"
                            href={mailboxOrgAttachmentUrl(detail.id, attachment.index)}
                            download
                          >
                            {t("mailboxOrg.download")}
                          </a>
                        </li>
                      ))}
                    </ul>
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
