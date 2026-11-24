import { FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";

/**
 * Strato's login form always shows an image CAPTCHA for the account this
 * runs against - no selector fix can solve that automatically. The
 * automation's browser session stays open server-side (strato_login_session.py)
 * while this modal asks a human to read the image and type the code back
 * in; submitting calls back into whichever automation (mailbox creation or
 * WordPress management) was in progress to resume it in that same session.
 *
 * Shared between ImapMailPage.tsx and WordPressPage.tsx rather than
 * duplicated, since it's pure UI with no feature-specific automation logic.
 */
export function StratoCaptchaModal({
  imageBase64,
  onSubmit,
  onCancel,
}: {
  imageBase64: string | null;
  onSubmit: (code: string) => Promise<void>;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!code.trim()) return;
    setBusy(true);
    setError("");
    try {
      await onSubmit(code.trim());
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="office-panel-backdrop" role="presentation" onClick={() => !busy && onCancel()}>
      <div
        className="office-panel strato-captcha-panel"
        role="dialog"
        aria-modal="true"
        style={{ maxWidth: 480 }}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="office-panel-header">
          <div>
            <p className="eyebrow">{t("stratoCaptcha.eyebrow")}</p>
            <h2>{t("stratoCaptcha.title")}</h2>
            <p className="muted">{t("stratoCaptcha.hint")}</p>
          </div>
          <div className="office-panel-actions">
            <button type="button" className="ghost-button" onClick={onCancel} disabled={busy}>
              {t("common.cancel")}
            </button>
          </div>
        </div>

        {imageBase64 ? (
          <img
            src={`data:image/png;base64,${imageBase64}`}
            alt={t("stratoCaptcha.imageAlt")}
            style={{
              maxWidth: "100%",
              maxHeight: "45vh",
              objectFit: "contain",
              border: "1px solid var(--border, #e4e7ec)",
              borderRadius: 8,
              marginBottom: 12,
            }}
          />
        ) : null}

        <form className="entra-setup-form" onSubmit={(event) => void handleSubmit(event)}>
          <label>
            {t("stratoCaptcha.codeLabel")}
            <input
              value={code}
              onChange={(event) => setCode(event.target.value)}
              placeholder="0802"
              autoComplete="off"
              autoFocus
              required
            />
          </label>
          {error ? <p className="error-text">{error}</p> : null}
          <button type="submit" className="primary-button" disabled={busy || !code.trim()}>
            {busy ? t("common.loading") : t("stratoCaptcha.submit")}
          </button>
        </form>
      </div>
    </div>
  );
}
