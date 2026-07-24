import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import {
  fetchPublishCalendar,
  type CalendarEvent,
  type PublishCalendar,
} from "../api/client";
import { EmptyState } from "./EmptyState";
import { LoadingState } from "./LoadingState";

function eventLink(event: CalendarEvent): string {
  if (event.type === "outlook_event" && event.external_url) {
    return event.external_url;
  }
  if (event.resource_type === "certificate" || event.type === "certificate_expiry") {
    return `/certificates/${event.resource_id}/edit`;
  }
  if (event.resource_type === "article" || event.type === "scheduled_publish") {
    return `/articles/${event.resource_id}/edit`;
  }
  return "/publish";
}

function eventTypeLabel(type: string, t: (key: string) => string): string {
  if (type === "scheduled_publish") return t("calendar.types.scheduled");
  if (type === "publication") return t("calendar.types.publication");
  if (type === "certificate_reminder") return t("calendar.types.reminder");
  if (type === "certificate_expiry") return t("calendar.types.expiry");
  if (type === "outlook_event") return t("calendar.types.outlook");
  return type;
}

export function PublishCalendarPanel({ compact = false }: { compact?: boolean }) {
  const { t, i18n } = useTranslation();
  const [calendar, setCalendar] = useState<PublishCalendar | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedDate, setSelectedDate] = useState<string>("");

  useEffect(() => {
    void (async () => {
      setLoading(true);
      try {
        const payload = await fetchPublishCalendar(compact ? 45 : 90, compact ? 7 : 14);
        setCalendar(payload.calendar);
        const today = new Date().toISOString().slice(0, 10);
        setSelectedDate(
          payload.calendar.by_date[today]
            ? today
            : Object.keys(payload.calendar.by_date).sort()[0] || today,
        );
      } catch (err) {
        setError(err instanceof Error ? err.message : t("common.error"));
      } finally {
        setLoading(false);
      }
    })();
  }, [compact, t]);

  const dayKeys = useMemo(() => Object.keys(calendar?.by_date || {}).sort(), [calendar]);
  const selectedEvents = calendar?.by_date[selectedDate] || [];

  if (loading) return <LoadingState />;
  if (error) return <p className="error-text">{error}</p>;
  if (!calendar || calendar.events.length === 0) {
    return <EmptyState message={t("calendar.empty")} icon="▦" />;
  }

  return (
    <div className={`publish-calendar ${compact ? "publish-calendar-compact" : ""}`}>
      <div className="publish-calendar-head">
        <div>
          <h2>{t("calendar.title")}</h2>
          <p className="muted">
            {calendar.range.start} → {calendar.range.end}
          </p>
        </div>
        {!compact ? (
          <Link to="/publish" className="ghost-button link-button">
            {t("calendar.openPublish")}
          </Link>
        ) : (
          <Link to="/calendar" className="ghost-button link-button">
            {t("calendar.openFull")}
          </Link>
        )}
      </div>

      <div className="calendar-day-strip" role="tablist" aria-label={t("calendar.title")}>
        {dayKeys.slice(0, compact ? 10 : 40).map((day) => (
          <button
            key={day}
            type="button"
            role="tab"
            aria-selected={selectedDate === day}
            className={selectedDate === day ? "calendar-day-chip active" : "calendar-day-chip"}
            onClick={() => setSelectedDate(day)}
          >
            <span>
              {new Date(`${day}T00:00:00`).toLocaleDateString(i18n.language, {
                month: "short",
                day: "numeric",
              })}
            </span>
            <strong>{calendar.by_date[day]?.length || 0}</strong>
          </button>
        ))}
      </div>

      <div className="list-stack calendar-event-list">
        {selectedEvents.map((event) => {
          const external = event.type === "outlook_event" && Boolean(event.external_url);
          const className = `calendar-event calendar-event-${event.type}`;
          const body = (
            <>
              <div className="list-card-title-row">
                <strong>{event.title}</strong>
                <span className="badge">{eventTypeLabel(event.type, t)}</span>
              </div>
              <p className="muted">
                {event.datetime
                  ? new Date(event.datetime).toLocaleString(i18n.language)
                  : event.date}
                {event.location ? ` · ${event.location}` : ""}
              </p>
            </>
          );
          if (external) {
            return (
              <a
                key={event.id}
                href={event.external_url}
                target="_blank"
                rel="noreferrer"
                className={className}
              >
                {body}
              </a>
            );
          }
          return (
            <Link key={event.id} to={eventLink(event)} className={className}>
              {body}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
