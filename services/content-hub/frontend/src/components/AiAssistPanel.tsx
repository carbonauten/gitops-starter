import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  draftArticleFromNotes,
  fetchAiStatus,
  rewriteArticleContent,
  summarizeArticleContent,
  translateArticleContent,
  type AiStatus,
  type RewriteTone,
} from "../api/client";

type AiAssistPanelProps = {
  title: string;
  content: string;
  disabled?: boolean;
  onApplyContent: (next: { title: string; content: string }) => void;
};

const TARGETS: Array<"de" | "en" | "zh-CN"> = ["de", "en", "zh-CN"];
const TONES: RewriteTone[] = ["professional", "concise", "friendly", "formal"];

export function AiAssistPanel({ title, content, disabled, onApplyContent }: AiAssistPanelProps) {
  const { t, i18n } = useTranslation();
  const [status, setStatus] = useState<AiStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [summary, setSummary] = useState("");
  const [notes, setNotes] = useState("");
  const [tone, setTone] = useState<RewriteTone>("professional");
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

  const uiLanguage = (["de", "en", "zh-CN"].includes(i18n.language) ? i18n.language : "de") as
    | "de"
    | "en"
    | "zh-CN";
  const hasArticleText = Boolean(title.trim() || content.trim());
  const aiReady = Boolean(status?.available);

  async function runAction(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await action();
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
        <span className={`ai-status-pill ${aiReady ? "ai-status-on" : "ai-status-off"}`}>
          {aiReady ? t("ai.available") : t("ai.unavailable")}
        </span>
      </div>

      {!aiReady ? <p className="muted">{t("ai.setupHint")}</p> : null}

      <div className="ai-assist-section">
        <h3>{t("ai.sectionTranslate")}</h3>
        <div className="ai-assist-row">
          <label className="ai-assist-field">
            <span>{t("ai.targetLanguage")}</span>
            <select
              value={targetLanguage}
              disabled={disabled || busy || !aiReady}
              onChange={(event) => setTargetLanguage(event.target.value as "de" | "en" | "zh-CN")}
            >
              {TARGETS.map((code) => (
                <option key={code} value={code}>
                  {t(`language.${code}`)}
                </option>
              ))}
            </select>
          </label>
          <div className="ai-assist-actions">
            <button
              type="button"
              className="primary-button"
              disabled={disabled || busy || !aiReady || !hasArticleText}
              onClick={() =>
                void runAction(async () => {
                  const translation = await translateArticleContent({
                    title,
                    content,
                    target_language: targetLanguage,
                  });
                  onApplyContent({ title: translation.title, content: translation.content });
                })
              }
            >
              {busy ? t("common.loading") : t("ai.translate")}
            </button>
            <button
              type="button"
              className="ghost-button"
              disabled={disabled || busy || !aiReady || !hasArticleText}
              onClick={() =>
                void runAction(async () => {
                  setSummary(await summarizeArticleContent({ title, content, language: uiLanguage }));
                })
              }
            >
              {t("ai.summarize")}
            </button>
          </div>
        </div>
      </div>

      <div className="ai-assist-section">
        <h3>{t("ai.sectionRewrite")}</h3>
        <div className="ai-assist-row">
          <label className="ai-assist-field">
            <span>{t("ai.tone")}</span>
            <select
              value={tone}
              disabled={disabled || busy || !aiReady}
              onChange={(event) => setTone(event.target.value as RewriteTone)}
            >
              {TONES.map((value) => (
                <option key={value} value={value}>
                  {t(`ai.tones.${value}`)}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className="primary-button"
            disabled={disabled || busy || !aiReady || !hasArticleText}
            onClick={() =>
              void runAction(async () => {
                const rewrite = await rewriteArticleContent({
                  title,
                  content,
                  tone,
                  language: uiLanguage,
                });
                onApplyContent({ title: rewrite.title, content: rewrite.content });
              })
            }
          >
            {t("ai.rewrite")}
          </button>
        </div>
      </div>

      <div className="ai-assist-section">
        <h3>{t("ai.sectionDraft")}</h3>
        <label className="ai-assist-field">
          <span>{t("ai.notesLabel")}</span>
          <textarea
            rows={5}
            value={notes}
            disabled={disabled || busy || !aiReady}
            placeholder={t("ai.notesPlaceholder")}
            onChange={(event) => setNotes(event.target.value)}
          />
        </label>
        <button
          type="button"
          className="primary-button"
          disabled={disabled || busy || !aiReady || !notes.trim()}
          onClick={() =>
            void runAction(async () => {
              const draft = await draftArticleFromNotes({
                notes,
                language: targetLanguage,
                title_hint: title,
              });
              onApplyContent({ title: draft.title, content: draft.content });
            })
          }
        >
          {t("ai.generateDraft")}
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
