import { FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import {
  fetchWordPressInstallations,
  fetchWordPressStatus,
  installWordPressAutomated,
  resumeWordPressInstallCaptcha,
  resumeWordPressInstallationsCaptcha,
  WordPressAutomationApiError,
  type WordPressInstallation,
  type WordPressStatus,
} from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";
import { StratoCaptchaModal } from "../components/StratoCaptchaModal";

type Mode = "flexibility" | "security";
type CaptchaPrompt = { kind: "install" | "list"; sessionId: string; imageBase64: string | null };

export function WordPressPage() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<WordPressStatus | null>(null);
  const [installations, setInstallations] = useState<WordPressInstallation[]>([]);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [loadingList, setLoadingList] = useState(false);
  const [listError, setListError] = useState("");
  const [listScreenshot, setListScreenshot] = useState<string | null>(null);

  const [installMode, setInstallMode] = useState<Mode>("security");
  const [installDomain, setInstallDomain] = useState("");
  const [installBusy, setInstallBusy] = useState(false);
  const [installError, setInstallError] = useState("");
  const [installScreenshot, setInstallScreenshot] = useState<string | null>(null);
  const [installNotice, setInstallNotice] = useState("");

  const [captchaPrompt, setCaptchaPrompt] = useState<CaptchaPrompt | null>(null);

  async function reloadStatus() {
    setLoadingStatus(true);
    try {
      const next = await fetchWordPressStatus();
      setStatus(next);
      if (!installDomain && next.domains.length > 0) setInstallDomain(next.domains[0]);
      if (next.configured) void reloadInstallations();
    } catch {
      setStatus(null);
    } finally {
      setLoadingStatus(false);
    }
  }

  async function reloadInstallations() {
    setLoadingList(true);
    setListError("");
    setListScreenshot(null);
    try {
      const outcome = await fetchWordPressInstallations();
      if (outcome.status === "captcha_required") {
        setCaptchaPrompt({ kind: "list", sessionId: outcome.session_id, imageBase64: outcome.captcha_image_base64 });
        return;
      }
      setInstallations(outcome.installations);
    } catch (err) {
      if (err instanceof WordPressAutomationApiError) {
        setListError(err.message);
        setListScreenshot(err.screenshotBase64);
      } else {
        setListError(err instanceof Error ? err.message : t("common.error"));
      }
    } finally {
      setLoadingList(false);
    }
  }

  useEffect(() => {
    void reloadStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleInstall(event: FormEvent) {
    event.preventDefault();
    setInstallBusy(true);
    setInstallError("");
    setInstallScreenshot(null);
    setInstallNotice("");
    try {
      const outcome = await installWordPressAutomated({ mode: installMode, domain: installDomain });
      if (outcome.status === "captcha_required") {
        setCaptchaPrompt({ kind: "install", sessionId: outcome.session_id, imageBase64: outcome.captcha_image_base64 });
        return;
      }
      setInstallNotice(t("wordpress.installSuccess", { domain: outcome.domain }));
      await reloadInstallations();
    } catch (err) {
      if (err instanceof WordPressAutomationApiError) {
        setInstallError(err.message);
        setInstallScreenshot(err.screenshotBase64);
      } else {
        setInstallError(err instanceof Error ? err.message : t("common.error"));
      }
    } finally {
      setInstallBusy(false);
    }
  }

  async function handleCaptchaSubmit(code: string) {
    if (!captchaPrompt) return;
    if (captchaPrompt.kind === "list") {
      try {
        const result = await resumeWordPressInstallationsCaptcha(captchaPrompt.sessionId, code);
        setInstallations(result);
        setCaptchaPrompt(null);
      } finally {
        setLoadingList(false);
      }
      return;
    }
    try {
      const result = await resumeWordPressInstallCaptcha(captchaPrompt.sessionId, code);
      setInstallNotice(t("wordpress.installSuccess", { domain: result.domain }));
      setCaptchaPrompt(null);
      await reloadInstallations();
    } finally {
      setInstallBusy(false);
    }
  }

  function handleCaptchaCancel() {
    setCaptchaPrompt(null);
    setLoadingList(false);
    setInstallBusy(false);
  }

  return (
    <section className="page">
      <header className="page-header">
        <h1>{t("wordpress.title")}</h1>
        <p className="muted">{t("wordpress.subtitle")}</p>
      </header>

      {captchaPrompt ? (
        <StratoCaptchaModal
          imageBase64={captchaPrompt.imageBase64}
          onSubmit={handleCaptchaSubmit}
          onCancel={handleCaptchaCancel}
        />
      ) : null}

      {loadingStatus ? <LoadingState /> : null}

      {!loadingStatus && !status?.configured ? (
        <div className="integration-connect-block">
          <p className="warning-text">{t("wordpress.notConfigured")}</p>
          <p className="muted">
            <Link to="/imap-mail">{t("wordpress.notConfiguredHint")}</Link>
          </p>
        </div>
      ) : null}

      {!loadingStatus && status?.configured ? (
        <>
          <div className="integration-connect-block">
            <div className="integration-connect-header">
              <strong>{t("wordpress.installTitle")}</strong>
            </div>
            <form className="entra-setup-form" onSubmit={(event) => void handleInstall(event)}>
              <div className="row-actions">
                <label>
                  {t("wordpress.mode")}
                  <select value={installMode} onChange={(event) => setInstallMode(event.target.value as Mode)}>
                    <option value="security">{t("wordpress.modeSecurity")}</option>
                    <option value="flexibility">{t("wordpress.modeFlexibility")}</option>
                  </select>
                </label>
                <label>
                  {t("wordpress.domain")}
                  {status.domains.length > 0 ? (
                    <select value={installDomain} onChange={(event) => setInstallDomain(event.target.value)}>
                      {status.domains.map((domain) => (
                        <option key={domain} value={domain}>
                          {domain}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      value={installDomain}
                      onChange={(event) => setInstallDomain(event.target.value)}
                      placeholder="carbonauten.com"
                      required
                      autoComplete="off"
                    />
                  )}
                </label>
              </div>
              <p className="muted">
                {installMode === "security" ? t("wordpress.modeSecurityHint") : t("wordpress.modeFlexibilityHint")}
              </p>
              <button type="submit" className="primary-button" disabled={installBusy || !installDomain}>
                {installBusy ? t("common.loading") : t("wordpress.install")}
              </button>
            </form>

            {installNotice ? (
              <p className="success-text" role="status">
                {installNotice}
              </p>
            ) : null}
            {installError ? (
              <div>
                <p className="error-text">{installError}</p>
                {installScreenshot ? (
                  <details>
                    <summary>{t("wordpress.automationScreenshotLabel")}</summary>
                    <img
                      src={`data:image/png;base64,${installScreenshot}`}
                      alt=""
                      style={{ maxWidth: "100%", border: "1px solid var(--border, #e4e7ec)", borderRadius: 8 }}
                    />
                  </details>
                ) : null}
                <p className="muted">
                  {t("wordpress.openStratoHint")}{" "}
                  <a href="https://www.strato.de/login" target="_blank" rel="noreferrer">
                    {t("wordpress.openStrato")}
                  </a>
                </p>
              </div>
            ) : null}
          </div>

          <div className="toolbar">
            <strong>{t("wordpress.installationsTitle")}</strong>
            <button type="button" className="ghost-button" disabled={loadingList} onClick={() => void reloadInstallations()}>
              {loadingList ? t("common.loading") : t("wordpress.refresh")}
            </button>
          </div>

          {listError ? (
            <div>
              <p className="error-text">{listError}</p>
              {listScreenshot ? (
                <details>
                  <summary>{t("wordpress.automationScreenshotLabel")}</summary>
                  <img
                    src={`data:image/png;base64,${listScreenshot}`}
                    alt=""
                    style={{ maxWidth: "100%", border: "1px solid var(--border, #e4e7ec)", borderRadius: 8 }}
                  />
                </details>
              ) : null}
              <p className="muted">
                {t("wordpress.openStratoHint")}{" "}
                <a href="https://www.strato.de/login" target="_blank" rel="noreferrer">
                  {t("wordpress.openStrato")}
                </a>
              </p>
            </div>
          ) : null}

          {loadingList ? <LoadingState /> : null}
          {!loadingList && !listError && installations.length === 0 ? (
            <EmptyState message={t("wordpress.empty")} icon="❖" />
          ) : null}

          <div className="list-stack">
            {!loadingList
              ? installations.map((installation) => (
                  <article key={installation.label} className="list-card">
                    <div>
                      <h2>{installation.label}</h2>
                      <p className="muted">{installation.application}</p>
                    </div>
                    <div className="list-card-actions">
                      {installation.link ? (
                        <a className="ghost-button" href={installation.link} target="_blank" rel="noreferrer">
                          {t("wordpress.openSite")}
                        </a>
                      ) : null}
                      {installation.wp_admin_url ? (
                        <a className="ghost-button" href={installation.wp_admin_url} target="_blank" rel="noreferrer">
                          {t("wordpress.openAdmin")}
                        </a>
                      ) : null}
                    </div>
                  </article>
                ))
              : null}
          </div>
        </>
      ) : null}
    </section>
  );
}
