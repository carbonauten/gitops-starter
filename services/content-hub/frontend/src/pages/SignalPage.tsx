import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  completeSignalLink,
  disconnectSignal,
  fetchSignalMessages,
  fetchSignalStatus,
  sendSignalMessage,
  startSignalLink,
  type SignalMessage,
  type SignalStatus,
} from "../api/client";

const LINK_POLL_INTERVAL_MS = 3000;
const LINK_POLL_TIMEOUT_MS = 120000;

export function SignalPage() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<SignalStatus | null>(null);
  const [messages, setMessages] = useState<SignalMessage[]>([]);
  const [qrDataUrl, setQrDataUrl] = useState("");
  const [linking, setLinking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [toNumber, setToNumber] = useState("");
  const [messageText, setMessageText] = useState("");
  const pollTimer = useRef<number | null>(null);

  const loadStatus = useCallback(async () => {
    try {
      setStatus(await fetchSignalStatus());
    } catch {
      setStatus(null);
    }
  }, []);

  const loadMessages = useCallback(async () => {
    try {
      setMessages(await fetchSignalMessages());
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    }
  }, [t]);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  useEffect(() => {
    if (status?.connected) {
      void loadMessages();
    }
  }, [status?.connected, loadMessages]);

  useEffect(() => {
    return () => {
      if (pollTimer.current) window.clearTimeout(pollTimer.current);
    };
  }, []);

  async function handleStartLink() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await startSignalLink();
      setQrDataUrl(result.qr_data_url);
      setLinking(true);
      pollForLink(Date.now());
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  function pollForLink(startedAt: number) {
    pollTimer.current = window.setTimeout(async () => {
      try {
        const result = await completeSignalLink();
        if (result.connected) {
          setLinking(false);
          setQrDataUrl("");
          setNotice(t("signal.connected"));
          await loadStatus();
          return;
        }
      } catch {
        // keep polling until timeout
      }
      if (Date.now() - startedAt > LINK_POLL_TIMEOUT_MS) {
        setLinking(false);
        setQrDataUrl("");
        setError(t("signal.linkTimedOut"));
        return;
      }
      pollForLink(startedAt);
    }, LINK_POLL_INTERVAL_MS);
  }

  async function handleDisconnect() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await disconnectSignal();
      setMessages([]);
      await loadStatus();
      setNotice(t("signal.disconnected"));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function handleSend(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await sendSignalMessage(toNumber.trim(), messageText.trim());
      setMessageText("");
      setNotice(t("signal.sent"));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  const serviceConfigured = Boolean(status?.service_configured);
  const connected = Boolean(status?.connected);

  return (
    <section className="page">
      <header className="page-header row-header">
        <div>
          <p className="eyebrow">{t("signal.eyebrow")}</p>
          <h1>{t("signal.pageTitle")}</h1>
          <p className="muted">{t("signal.pageSubtitle")}</p>
        </div>
      </header>

      <div className="integration-connect-block">
        <div className="integration-connect-header">
          <strong>{t("signal.title")}</strong>
          {connected ? (
            <span className="integration-badge integration-badge-connected">
              {status?.account || t("mail.connected")}
            </span>
          ) : (
            <span className="integration-badge">{t("mail.notConnected")}</span>
          )}
        </div>
        <p className="muted">{t("signal.hint")}</p>

        {!serviceConfigured ? (
          <p className="warning-text">{t("signal.serviceNotConfigured")}</p>
        ) : connected ? (
          <button type="button" className="ghost-button" disabled={busy} onClick={() => void handleDisconnect()}>
            {t("signal.disconnect")}
          </button>
        ) : linking ? (
          <div className="signal-link-panel">
            {qrDataUrl ? (
              <img src={qrDataUrl} alt={t("signal.qrAlt")} className="signal-qr-image" />
            ) : null}
            <p className="muted">{t("signal.scanHint")}</p>
          </div>
        ) : (
          <button type="button" className="primary-button" disabled={busy} onClick={() => void handleStartLink()}>
            {t("signal.connect")}
          </button>
        )}

        {notice ? <p className="success-text">{notice}</p> : null}
        {error ? <p className="error-text">{error}</p> : null}
      </div>

      {connected ? (
        <>
          <div className="integration-connect-block">
            <strong>{t("signal.sendTitle")}</strong>
            <form className="entra-setup-form" onSubmit={(event) => void handleSend(event)}>
              <label>
                {t("signal.toLabel")}
                <input
                  value={toNumber}
                  onChange={(event) => setToNumber(event.target.value)}
                  placeholder="+49170..."
                  required
                />
              </label>
              <label>
                {t("signal.messageLabel")}
                <textarea
                  value={messageText}
                  onChange={(event) => setMessageText(event.target.value)}
                  rows={3}
                  required
                />
              </label>
              <button type="submit" className="primary-button" disabled={busy}>
                {t("signal.sendButton")}
              </button>
            </form>
          </div>

          <div className="integration-connect-block">
            <div className="integration-connect-header">
              <strong>{t("signal.inboxTitle")}</strong>
              <button type="button" className="ghost-button" onClick={() => void loadMessages()}>
                {t("signal.refresh")}
              </button>
            </div>
            {messages.length === 0 ? (
              <p className="muted">{t("signal.noMessages")}</p>
            ) : (
              <ul className="signal-message-list">
                {messages.map((message) => (
                  <li key={message.id} className="signal-message-item">
                    <div className="signal-message-meta">
                      <strong>{message.from_name}</strong>
                      <span className="muted">{message.received_at}</span>
                    </div>
                    <p>{message.text}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      ) : null}
    </section>
  );
}
