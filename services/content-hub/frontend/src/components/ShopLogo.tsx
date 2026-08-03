type ShopLogoProps = {
  brand?: string;
  company?: string;
  size?: "sm" | "md" | "lg" | "hero";
  showCompany?: boolean;
  stacked?: boolean;
};

export function ShopLogo({
  brand = "FuckCo2",
  company = "carbonauten GmbH",
  size = "md",
  showCompany = true,
  stacked = false,
}: ShopLogoProps) {
  return (
    <span className={`shop-logo shop-logo-${size}${stacked ? " shop-logo-stacked" : ""}`}>
      <span className="shop-logo-mark" aria-hidden="true">
        <svg viewBox="0 0 64 64" role="img" focusable="false">
          <defs>
            <linearGradient id="shopLogoGrad" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#c6f55a" />
              <stop offset="100%" stopColor="#7bcf3a" />
            </linearGradient>
          </defs>
          <circle cx="32" cy="32" r="28" fill="none" stroke="url(#shopLogoGrad)" strokeWidth="3" />
          <path
            d="M18 40c4-12 10-20 14-24 4 4 10 12 14 24"
            fill="none"
            stroke="url(#shopLogoGrad)"
            strokeWidth="3.2"
            strokeLinecap="round"
          />
          <path d="M14 34h36" stroke="url(#shopLogoGrad)" strokeWidth="3.2" strokeLinecap="round" />
          <circle cx="32" cy="34" r="4.5" fill="#c6f55a" />
        </svg>
      </span>
      <span className="shop-logo-text">
        <span className="shop-logo-wordmark">
          <span className="shop-logo-fuck">Fuck</span>
          <span className="shop-logo-co2">
            CO<sub>2</sub>
          </span>
        </span>
        {showCompany ? (
          <span className="shop-logo-company">
            {company}
          </span>
        ) : null}
      </span>
      <span className="visually-hidden">
        {brand} — {company}
      </span>
    </span>
  );
}
