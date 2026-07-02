import { useTranslation } from "react-i18next";

import { supportedLanguages, type AppLanguage } from "../i18n";
import { useAuth } from "../hooks/useAuth";

const labels: Record<AppLanguage, string> = {
  de: "DE",
  en: "EN",
  "zh-CN": "中文",
};

export function LanguageSwitch() {
  const { i18n } = useTranslation();
  const { setLanguage } = useAuth();
  const current = (supportedLanguages.includes(i18n.language as AppLanguage)
    ? i18n.language
    : "en") as AppLanguage;

  return (
    <div className="language-switch" role="group" aria-label="Language">
      {supportedLanguages.map((language) => (
        <button
          key={language}
          type="button"
          className={language === current ? "active" : ""}
          onClick={() => void setLanguage(language)}
        >
          {labels[language]}
        </button>
      ))}
    </div>
  );
}
