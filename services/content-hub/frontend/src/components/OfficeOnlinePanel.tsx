import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import type { OfficeSession } from "../api/client";

type Props = {
  session: OfficeSession | null;
  loading?: boolean;
  error?: string;
  onClose: () => void;
};

export function OfficeOnlinePanel({ session, loading = false, error = "", onClose }: Props) {
  const { t } = useTranslation();
  const [iframeFailed, setIframeFailed] = useState(false);

  useEffect(() => {
    setIframeFailed(false);
    if (!session?.embed_url) {
      setIframeFailed(true);
      return;
    }
    const timer = window.setTimeout(() => {
      // If the tenant blocks framing, users still have the edit/open actions.
      setIframeFailed(false);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [session?.embed_url, session?.item_id]);

  if (!session && !loading && !error) return null;

  return (
    <div className="office-panel-backdrop" role="dialog" aria-modal="true" aria-label={t("files.officeTitle")}>
      <div className="office-panel">
        <header className="office-panel-header">
          <div>
            <p className="eyebrow">{t("files.officeTitle")}</p>
            <h2>{session?.name || t("files.officeLoading")}</h2>
          </div>
          <div className="office-panel-actions">
            {session?.can_edit && session.edit_url ? (
              <a
                className="primary-button integration-connect-button"
                href={session.edit_url}
                target="_blank"
                rel="noreferrer"
              >
                {t("files.officeEdit")}
              </a>
            ) : null}
            {session?.edit_url && !session.can_edit ? (
              <a
                className="ghost-button link-button"
                href={session.edit_url}
                target="_blank"
                rel="noreferrer"
              >
                {t("files.openExternal")}
              </a>
            ) : null}
            <button type="button" className="ghost-button" onClick={onClose}>
              {t("common.close")}
            </button>
          </div>
        </header>

        {loading ? <p className="muted">{t("files.officeLoading")}</p> : null}
        {error ? <p className="error-text">{error}</p> : null}

        {!loading && session ? (
          <>
            {session.mock ? <p className="muted">{t("files.officeMockHint")}</p> : null}
            {!session.can_edit && session.source === "platform" ? (
              <p className="muted">{t("files.officePlatformHint")}</p>
            ) : null}
            {session.embed_url && !iframeFailed ? (
              <iframe
                className="office-panel-frame"
                title={session.name}
                src={session.embed_url}
                allow="fullscreen"
                onError={() => setIframeFailed(true)}
              />
            ) : (
              <div className="office-panel-fallback">
                <p>{t("files.officeEmbedBlocked")}</p>
                {session.edit_url ? (
                  <a
                    className="primary-button integration-connect-button"
                    href={session.edit_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {session.can_edit ? t("files.officeEdit") : t("files.openExternal")}
                  </a>
                ) : null}
              </div>
            )}
          </>
        ) : null}
      </div>
    </div>
  );
}
