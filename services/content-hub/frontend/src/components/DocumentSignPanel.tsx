import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { fetchFileSignStatus, type DocumentSignature, type DocumentSignResponse } from "../api/client";

type Props = {
  fileId: string | null;
  result: DocumentSignResponse | null;
  loading?: boolean;
  error?: string;
  onClose: () => void;
  onCompleted?: () => void;
  // Documenso may gate embedded (iframe) signing behind a paid "Teams" plan
  // even for self-hosted instances - this is NOT verified yet against a real
  // instance (see PR description). Flip this to always use window.open()
  // (the "In neuem Tab öffnen" link below) instead of the iframe if embedded
  // signing turns out to be license-gated.
  forceExternal?: boolean;
};

const POLL_INTERVAL_MS = 4000;

export function DocumentSignPanel({
  fileId,
  result,
  loading = false,
  error = "",
  onClose,
  onCompleted,
  forceExternal = false,
}: Props) {
  const { t } = useTranslation();
  const [iframeFailed, setIframeFailed] = useState(false);
  const [status, setStatus] = useState<DocumentSignature | null>(result?.signature ?? null);
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    setIframeFailed(false);
    setStatus(result?.signature ?? null);
  }, [result]);

  // Poll for completion while pending: Documenso's real postMessage/webhook
  // event format isn't confirmed yet, so this is the reliable fallback.
  useEffect(() => {
    if (pollRef.current) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
    if (!fileId || !status || status.status !== "pending") {
      return;
    }
    pollRef.current = window.setInterval(() => {
      void fetchFileSignStatus(fileId)
        .then((next) => {
          if (!next) return;
          setStatus(next);
          if (next.status === "completed") {
            onCompleted?.();
          }
        })
        .catch(() => {
          // transient polling error - try again on the next tick
        });
    }, POLL_INTERVAL_MS);
    return () => {
      if (pollRef.current) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [fileId, status, onCompleted]);

  if (!result && !loading && !error) return null;

  const externalUrl = result?.external_signing_url || result?.signing_url || "";
  const useIframe = !forceExternal && Boolean(result?.signing_url) && !iframeFailed;
  const isFinal = status?.status === "completed" || status?.status === "rejected" || status?.status === "cancelled";

  return (
    <div className="office-panel-backdrop" role="dialog" aria-modal="true" aria-label={t("files.signTitle")}>
      <div className="office-panel">
        <header className="office-panel-header">
          <div>
            <p className="eyebrow">{t("files.signTitle")}</p>
            <h2>
              {status?.status === "completed"
                ? t("files.signCompleted")
                : status?.status === "rejected"
                  ? t("files.signRejected")
                  : status?.status === "cancelled"
                    ? t("files.signCancelled")
                    : t("files.signPending")}
            </h2>
          </div>
          <div className="office-panel-actions">
            {externalUrl && !isFinal ? (
              <a
                className="primary-button integration-connect-button"
                href={externalUrl}
                target="_blank"
                rel="noreferrer"
              >
                {t("files.signOpenExternal")}
              </a>
            ) : null}
            <button type="button" className="ghost-button" onClick={onClose}>
              {t("common.close")}
            </button>
          </div>
        </header>

        {loading ? <p className="muted">{t("files.signLoading")}</p> : null}
        {error ? <p className="error-text">{error}</p> : null}

        {!loading && result ? (
          <>
            {status?.status === "completed" ? (
              <p className="success-text" role="status">
                {t("files.signCompletedHint")}
              </p>
            ) : status?.status === "rejected" ? (
              <p className="error-text">{t("files.signRejectedHint")}</p>
            ) : status?.status === "cancelled" ? (
              <p className="error-text">{t("files.signCancelledHint")}</p>
            ) : useIframe ? (
              <iframe
                className="office-panel-frame"
                title={t("files.signTitle")}
                src={result.signing_url ?? undefined}
                allow="fullscreen"
                onError={() => setIframeFailed(true)}
              />
            ) : (
              <div className="office-panel-fallback">
                <p>{t("files.signEmbedBlocked")}</p>
                {externalUrl ? (
                  <a
                    className="primary-button integration-connect-button"
                    href={externalUrl}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {t("files.signOpenExternal")}
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
