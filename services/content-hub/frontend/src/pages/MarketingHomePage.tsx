import { useState } from "react";

import { MarketingHeader } from "../components/marketing/MarketingHeader";
import { MarketingFooter } from "../components/marketing/MarketingFooter";
import { WorldMapGraphic } from "../components/marketing/WorldMapGraphic";
import { TechIllustration } from "../components/marketing/TechIllustration";
import { about, contact, hero, products, projects, technology } from "../content/marketingSite";

export function MarketingHomePage() {
  const [submitted, setSubmitted] = useState(false);

  return (
    <div className="marketing-site">
      <MarketingHeader />

      <section className="mk-hero">
        <div className="mk-hero-inner">
          <h1>{hero.headline}</h1>
        </div>
      </section>

      <section id="ueber" className="mk-section mk-section-light">
        <div className="mk-section-inner mk-about-grid">
          <div>
            <h2>{about.heading}</h2>
            <p>{about.paragraph}</p>
          </div>
          <div>
            <h2>{about.worldwideHeading}</h2>
            <WorldMapGraphic />
            <p style={{ marginTop: "1rem" }}>{about.worldwideParagraph}</p>
          </div>
        </div>
      </section>

      <section id="produkte" className="mk-section mk-section-dark">
        <div className="mk-section-inner">
          <h2>Unsere Produkte</h2>
          <div className="mk-products-grid">
            {products.map((product) => (
              <div className="mk-product-card" key={product.title}>
                <h3>{product.title}</h3>
                <p>{product.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="technologie" className="mk-section mk-section-dark">
        <div className="mk-section-inner mk-tech-grid">
          <TechIllustration />
          <div>
            <h2>{technology.heading}</h2>
            <p style={{ color: "#dce8d6" }}>{technology.paragraph}</p>
          </div>
        </div>
      </section>

      <section id="projekte" className="mk-section mk-section-light">
        <div className="mk-section-inner">
          <h2>Projekte</h2>
          <div className="mk-projects-grid">
            {projects.map((project) => (
              <div className="mk-project-card" key={project.title}>
                <h3>{project.title}</h3>
                <p>{project.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="kontakt" className="mk-section mk-section-light">
        <div className="mk-section-inner">
          <h2>{contact.heading}</h2>
          {submitted ? (
            <p>Danke, wir melden uns.</p>
          ) : (
            <form
              className="mk-contact-form"
              onSubmit={(event) => {
                event.preventDefault();
                setSubmitted(true);
              }}
            >
              <div className="mk-contact-row">
                <label>
                  {contact.nameLabel}
                  <input type="text" name="name" required />
                </label>
                <label>
                  {contact.emailLabel}
                  <input type="email" name="email" required />
                </label>
              </div>
              <label>
                {contact.messageLabel}
                <textarea name="message" required />
              </label>
              <button type="submit" className="mk-cta" style={{ justifySelf: "start" }}>
                {contact.submit}
              </button>
            </form>
          )}
        </div>
      </section>

      <MarketingFooter />
    </div>
  );
}
