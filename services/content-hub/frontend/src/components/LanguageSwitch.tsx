import { useTranslation } from "react-i18next";

import { supportedLanguages, type AppLanguage } from "../i18n";
import { useOptionalAuth } from "../hooks/useAuth";

const labels: Record<AppLanguage, string> = {
  de: "DE",
  en: "EN",
  "zh-CN": "中文",
};

export function LanguageSwitch() {
  const { i18n } = useTranslation();
  const auth = useOptionalAuth();
  const current = (supportedLanguages.includes(i18n.language as AppLanguage)
    ? i18n.language
    : "en") as AppLanguage;

  async function changeLanguage(language: AppLanguage) {
    if (auth) {
      await auth.setLanguage(language);
      return;
    }
    await i18n.changeLanguage(language);
    window.localStorage.setItem("content-hub-language", language);
  }

  return (
    <div className="language-switch" role="group" aria-label="Language">
      {supportedLanguages.map((language) => (
        <button
          key={language}
          type="button"
          className={language === current ? "active" : ""}
          onClick={() => void changeLanguage(language)}
        >
          {labels[language]}
        </button>
      ))}
    </div>
  );
}
