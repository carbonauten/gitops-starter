import { useTranslation } from "react-i18next";

const STORAGE_KEY = "content-hub-onboarding-dismissed";

export function OnboardingTips() {
  const { t } = useTranslation();
  if (localStorage.getItem(STORAGE_KEY) === "true") {
    return null;
  }

  return (
    <div className="info-banner onboarding-banner">
      <div>
        <strong>{t("onboarding.title")}</strong>
        <ol className="onboarding-list">
          <li>{t("onboarding.step1")}</li>
          <li>{t("onboarding.step2")}</li>
          <li>{t("onboarding.step3")}</li>
        </ol>
      </div>
      <button
        type="button"
        className="ghost-button"
        onClick={() => localStorage.setItem(STORAGE_KEY, "true")}
      >
        {t("onboarding.dismiss")}
      </button>
    </div>
  );
}
