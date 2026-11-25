import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { createMeeting, fetchMeetings, type Meeting } from "../api/client";
import { useAuth } from "../hooks/useAuth";

const JITSI_SCRIPT_SRC = "https://meet.jit.si/external_api.js";

declare global {
  interface Window {
    JitsiMeetExternalAPI?: new (domain: string, options: Record<string, unknown>) => {
      dispose: () => void;
    };
  }
}

let jitsiScriptPromise: Promise<void> | null = null;

function loadJitsiScript(): Promise<void> {
  if (window.JitsiMeetExternalAPI) return Promise.resolve();
  if (!jitsiScriptPromise) {
    jitsiScriptPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = JITSI_SCRIPT_SRC;
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error("jitsi_script_failed"));
      document.body.appendChild(script);
    });
  }
  return jitsiScriptPromise;
}

export function MeetingsPage() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [activeRoom, setActiveRoom] = useState<Meeting | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const containerRef = useRef<HTMLDivElement | null>(null);
  const apiRef = useRef<{ dispose: () => void } | null>(null);

  const loadMeetings = useCallback(async () => {
    try {
      setMeetings(await fetchMeetings());
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    }
  }, [t]);

  useEffect(() => {
    void loadMeetings();
  }, [loadMeetings]);

  const joinRoom = useCallback(
    async (meeting: Meeting) => {
      setError("");
      try {
        await loadJitsiScript();
      } catch {
        setError(t("meetings.scriptFailed"));
        return;
      }
      if (apiRef.current) {
        apiRef.current.dispose();
        apiRef.current = null;
      }
      if (!window.JitsiMeetExternalAPI || !containerRef.current) return;
      apiRef.current = new window.JitsiMeetExternalAPI(meeting.domain, {
        roomName: meeting.room_name,
        parentNode: containerRef.current,
        width: "100%",
        height: 560,
        userInfo: user ? { displayName: user.name } : undefined,
      });
      setActiveRoom(meeting);
    },
    [t, user],
  );

  useEffect(() => {
    return () => {
      apiRef.current?.dispose();
    };
  }, []);

  async function handleStart() {
    setBusy(true);
    setError("");
    try {
      const meeting = await createMeeting();
      await joinRoom(meeting);
      await loadMeetings();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  function handleLeave() {
    apiRef.current?.dispose();
    apiRef.current = null;
    setActiveRoom(null);
  }

  async function handleCopyLink(url: string) {
    try {
      await navigator.clipboard.writeText(url);
    } catch {
      // clipboard may be unavailable; link is still shown in the list
    }
  }

  return (
    <section className="page">
      <header className="page-header row-header">
        <div>
          <p className="eyebrow">{t("meetings.eyebrow")}</p>
          <h1>{t("meetings.pageTitle")}</h1>
          <p className="muted">{t("meetings.pageSubtitle")}</p>
        </div>
      </header>

      <div className="integration-connect-block">
        <div className="integration-connect-header">
          <strong>{t("meetings.title")}</strong>
          {!activeRoom ? (
            <button type="button" className="primary-button" disabled={busy} onClick={() => void handleStart()}>
              {t("meetings.start")}
            </button>
          ) : (
            <button type="button" className="ghost-button" onClick={handleLeave}>
              {t("meetings.leave")}
            </button>
          )}
        </div>
        {error ? <p className="error-text">{error}</p> : null}
        <div ref={containerRef} className={activeRoom ? "meeting-call-frame" : "meeting-call-frame is-empty"} />
      </div>

      <div className="integration-connect-block">
        <div className="integration-connect-header">
          <strong>{t("meetings.recentTitle")}</strong>
          <button type="button" className="ghost-button" onClick={() => void loadMeetings()}>
            {t("signal.refresh")}
          </button>
        </div>
        {meetings.length === 0 ? (
          <p className="muted">{t("meetings.noMeetings")}</p>
        ) : (
          <ul className="meeting-list">
            {meetings.map((meeting) => (
              <li key={meeting.id} className="meeting-list-item">
                <div>
                  <strong>{meeting.title || meeting.room_name}</strong>
                  <p className="muted">{t("meetings.startedBy", { name: meeting.created_by_name })}</p>
                </div>
                <div className="row-actions">
                  <button type="button" className="ghost-button" onClick={() => void handleCopyLink(meeting.url)}>
                    {t("meetings.copyLink")}
                  </button>
                  <button type="button" className="primary-button" onClick={() => void joinRoom(meeting)}>
                    {t("meetings.join")}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
