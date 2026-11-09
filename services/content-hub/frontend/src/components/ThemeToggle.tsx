import { useTranslation } from "react-i18next";

import { useTheme, type ThemePreference } from "../hooks/useTheme";

const ICONS: Record<ThemePreference, string> = {
  light: "☀",
  dark: "☾",
  system: "◐",
};

export function ThemeToggle() {
  const { t } = useTranslation();
  const { preference, cycle } = useTheme();

  const labels: Record<ThemePreference, string> = {
    light: t("nav.themeLight"),
    dark: t("nav.themeDark"),
    system: t("nav.themeSystem"),
  };

  return (
    <button
      type="button"
      className="ghost-button theme-toggle"
      onClick={cycle}
      title={labels[preference]}
      aria-label={labels[preference]}
    >
      <span aria-hidden="true">{ICONS[preference]}</span>
    </button>
  );
}
