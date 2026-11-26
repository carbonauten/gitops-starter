import { MarketingHeader } from "../components/marketing/MarketingHeader";
import { MarketingFooter } from "../components/marketing/MarketingFooter";
import { datenschutz, impressum } from "../content/marketingSite";

type LegalPageProps = {
  variant: "impressum" | "datenschutz";
};

export function LegalPage({ variant }: LegalPageProps) {
  const content = variant === "impressum" ? impressum : datenschutz;

  return (
    <div className="marketing-site mk-legal-wrapper">
      <MarketingHeader />
      <div className="mk-legal-hero">
        <div className="mk-legal-hero-inner">{content.title}</div>
      </div>
      <div className="mk-legal-card">
        {content.sections.map((section) => (
          <section key={section.heading}>
            <h2>{section.heading}</h2>
            {section.lines.map((line, index) => (
              <p key={index}>{line || " "}</p>
            ))}
          </section>
        ))}
      </div>
      <MarketingFooter />
    </div>
  );
}
