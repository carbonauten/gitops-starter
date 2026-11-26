import { useTranslation } from "react-i18next";

type BrandLogoProps = {
  size?: "sm" | "md" | "lg";
  showTagline?: boolean;
};

export function BrandLogo({ size = "md", showTagline = true }: BrandLogoProps) {
  const { t } = useTranslation();

  return (
    <div className={`brand-logo brand-logo-${size}`}>
      <img
        src="/logo-signet-farbig.png"
        alt={t("app.name")}
        className="brand-logo-image brand-logo-image-light"
      />
      <img
        src="/logo-signet-weiss.png"
        alt={t("app.name")}
        className="brand-logo-image brand-logo-image-dark"
      />
      <div>
        <p className="brand-name">{t("app.name")}</p>
        {showTagline ? <p className="brand-tagline">{t("app.tagline")}</p> : null}
      </div>
    </div>
  );
}
