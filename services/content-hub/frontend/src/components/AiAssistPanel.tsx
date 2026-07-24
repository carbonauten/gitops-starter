import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  fetchAiStatus,
  summarizeArticleContent,
  translateArticleContent,
  type AiStatus,
} from "../api/client";

type AiAssistPanelProps = {
  title: string;
  content: string;
  disabled?: boolean;
  onApplyTranslation: (next: { title: string; content: string }) => void;
};

const TARGETS: Array<"de" | "en" | "zh-CN"> = ["de", "en", "zh-CN"];

export function AiAssistPanel({ title, content, disabled, onApplyTranslation }: AiAssistPanelProps) {
  const { t, i18n } = useTranslation();
  const [status, setStatus] = useState<AiStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [summary, setSummary] = useState("");
  const [targetLanguage, setTargetLanguage] = useState<"de" | "en" | "zh-CN">(
    (["de", "en", "zh-CN"].includes(i18n.language) ? i18n.language : "en") as "de" | "en" | "zh-CN",
  );

  useEffect(() => {
    void (async () => {
      try {
        setStatus(await fetchAiStatus());
      } catch {
        setStatus({ available: false, features: [], assistant_name: "Ask Carbonauten" });
      }
    })();
  }, []);

  async function handleTranslate() {
    setBusy(true);
    setError("");
    try {
      const translation = await translateArticleContent({
        title,
        content,
        target_language: targetLanguage,
      });
      onApplyTranslation({ title: translation.title, content: translation.content });
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function handleSummarize() {
    setBusy(true);
    setError("");
    try {
      const language = (["de", "en", "zh-CN"].includes(i18n.language) ? i18n.language : "de") as
        | "de"
        | "en"
        | "zh-CN";
      setSummary(await summarizeArticleContent({ title, content, language }));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className="ai-assist-panel">
      <div className="ai-assist-head">
        <div>
          <p className="eyebrow">{status?.assistant_name || t("ai.assistantName")}</p>
          <h2>{t("ai.panelTitle")}</h2>
          <p className="muted">{t("ai.panelSubtitle")}</p>
        </div>
        <span className={`ai-status-pill ${status?.available ? "ai-status-on" : "ai-status-off"}`}>
          {status?.available ? t("ai.available") : t("ai.unavailable")}
        </span>
      </div>

      {!status?.available ? <p className="muted">{t("ai.setupHint")}</p> : null}

      <div className="ai-assist-row">
        <label className="ai-assist-field">
          <span>{t("ai.targetLanguage")}</span>
          <select
            value={targetLanguage}
            disabled={disabled || busy || !status?.available}
            onChange={(event) => setTargetLanguage(event.target.value as "de" | "en" | "zh-CN")}
          >
            {TARGETS.map((code) => (
              <option key={code} value={code}>
                {t(`language.${code}`)}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="primary-button"
          disabled={disabled || busy || !status?.available || (!title.trim() && !content.trim())}
          onClick={() => void handleTranslate()}
        >
          {busy ? t("common.loading") : t("ai.translate")}
        </button>
        <button
          type="button"
          className="ghost-button"
          disabled={disabled || busy || !status?.available || (!title.trim() && !content.trim())}
          onClick={() => void handleSummarize()}
        >
          {t("ai.summarize")}
        </button>
      </div>

      {error ? <p className="error-text">{error}</p> : null}
      {summary ? (
        <div className="ai-summary-box">
          <strong>{t("ai.summaryTitle")}</strong>
          <pre>{summary}</pre>
        </div>
      ) : null}
    </aside>
  );
}
