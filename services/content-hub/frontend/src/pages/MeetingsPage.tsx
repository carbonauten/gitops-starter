import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  createMeeting,
  fetchMeetings,
  fetchUpcomingMeetings,
  scheduleMeeting,
  type Meeting,
} from "../api/client";
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

function defaultScheduleDate(): string {
  const now = new Date();
  now.setMinutes(now.getMinutes() + 30);
  return now.toISOString().slice(0, 10);
}

function defaultScheduleTime(): string {
  const now = new Date();
  now.setMinutes(now.getMinutes() + 30);
  return now.toISOString().slice(11, 16);
}

export function MeetingsPage() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [upcoming, setUpcoming] = useState<Meeting[]>([]);
  const [activeRoom, setActiveRoom] = useState<Meeting | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const containerRef = useRef<HTMLDivElement | null>(null);
  const apiRef = useRef<{ dispose: () => void } | null>(null);

  const [showSchedule, setShowSchedule] = useState(false);
  const [scheduleTitle, setScheduleTitle] = useState("");
  const [scheduleDate, setScheduleDate] = useState(defaultScheduleDate);
  const [scheduleTime, setScheduleTime] = useState(defaultScheduleTime);
  const [scheduleDuration, setScheduleDuration] = useState(30);
  const [scheduleAttendees, setScheduleAttendees] = useState("");

  const loadMeetings = useCallback(async () => {
    try {
      setMeetings(await fetchMeetings());
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    }
  }, [t]);

  const loadUpcoming = useCallback(async () => {
    try {
      setUpcoming(await fetchUpcomingMeetings());
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    }
  }, [t]);

  useEffect(() => {
    void loadMeetings();
    void loadUpcoming();
  }, [loadMeetings, loadUpcoming]);

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

  async function handleSchedule(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const scheduledAt = new Date(`${scheduleDate}T${scheduleTime}:00`).toISOString();
      const result = await scheduleMeeting({
        title: scheduleTitle,
        scheduled_at: scheduledAt,
        duration_minutes: scheduleDuration,
        attendees: scheduleAttendees,
      });
      if (result.outlook_invited && result.mailbox_org_invited) {
        setNotice(`${t("meetings.scheduledWithOutlook")} ${t("meetings.scheduledWithMailboxOrg")}`);
      } else if (result.outlook_invited) {
        setNotice(t("meetings.scheduledWithOutlook"));
      } else if (result.mailbox_org_invited) {
        setNotice(t("meetings.scheduledWithMailboxOrg"));
      } else {
        setNotice(t("meetings.scheduled"));
      }
      setScheduleTitle("");
      setScheduleAttendees("");
      setShowSchedule(false);
      await loadUpcoming();
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
        {notice ? <p className="success-text">{notice}</p> : null}
        <div ref={containerRef} className={activeRoom ? "meeting-call-frame" : "meeting-call-frame is-empty"} />
      </div>

      <div className="integration-connect-block">
        <div className="integration-connect-header">
          <strong>{t("meetings.scheduleTitle")}</strong>
          <button type="button" className="ghost-button" onClick={() => setShowSchedule((value) => !value)}>
            {showSchedule ? t("common.close") : t("meetings.scheduleButton")}
          </button>
        </div>
        <p className="muted">{t("meetings.scheduleHint")}</p>
        {showSchedule ? (
          <form className="entra-setup-form" onSubmit={(event) => void handleSchedule(event)}>
            <label>
              {t("meetings.scheduleTitleLabel")}
              <input value={scheduleTitle} onChange={(event) => setScheduleTitle(event.target.value)} />
            </label>
            <div className="row-actions">
              <label>
                {t("meetings.scheduleDateLabel")}
                <input
                  type="date"
                  value={scheduleDate}
                  onChange={(event) => setScheduleDate(event.target.value)}
                  required
                />
              </label>
              <label>
                {t("meetings.scheduleTimeLabel")}
                <input
                  type="time"
                  value={scheduleTime}
                  onChange={(event) => setScheduleTime(event.target.value)}
                  required
                />
              </label>
              <label>
                {t("meetings.scheduleDurationLabel")}
                <input
                  type="number"
                  min={5}
                  max={480}
                  value={scheduleDuration}
                  onChange={(event) => setScheduleDuration(Number(event.target.value) || 30)}
                />
              </label>
            </div>
            <label>
              {t("meetings.scheduleAttendeesLabel")}
              <input
                value={scheduleAttendees}
                onChange={(event) => setScheduleAttendees(event.target.value)}
                placeholder="anna@example.com, ben@example.com"
              />
              <span className="muted">{t("meetings.scheduleAttendeesHint")}</span>
            </label>
            <button type="submit" className="primary-button" disabled={busy}>
              {t("meetings.scheduleSubmit")}
            </button>
          </form>
        ) : null}
      </div>

      {upcoming.length > 0 ? (
        <div className="integration-connect-block">
          <div className="integration-connect-header">
            <strong>{t("meetings.upcomingTitle")}</strong>
            <button type="button" className="ghost-button" onClick={() => void loadUpcoming()}>
              {t("signal.refresh")}
            </button>
          </div>
          <ul className="meeting-list">
            {upcoming.map((meeting) => (
              <li key={meeting.id} className="meeting-list-item">
                <div>
                  <strong>{meeting.title || meeting.room_name}</strong>
                  <p className="muted">
                    {meeting.scheduled_at ? new Date(meeting.scheduled_at).toLocaleString() : ""}
                    {" · "}
                    {t("meetings.startedBy", { name: meeting.created_by_name })}
                  </p>
                </div>
                <div className="row-actions">
                  <a className="ghost-button link-button" href={meeting.ics_url} download>
                    {t("meetings.downloadIcs")}
                  </a>
                  <button type="button" className="ghost-button" onClick={() => void handleCopyLink(meeting.url)}>
                    {t("meetings.copyLink")}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

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
