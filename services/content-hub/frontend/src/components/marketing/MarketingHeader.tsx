import { Link } from "react-router-dom";

import wortmarkeWeiss from "../../assets/elphen/wortmarke-weiss.png";
import { nav } from "../../content/marketingSite";

export function MarketingHeader() {
  return (
    <header className="mk-header">
      <div className="mk-header-inner">
        <Link to="/" className="mk-logo">
          <img src={wortmarkeWeiss} alt="elphen" />
          <span className="mk-logo-tagline">{nav.brandTagline}</span>
        </Link>
        <nav className="mk-nav">
          <ul className="mk-nav-links">
            {nav.links.map((item) => (
              <li key={item.href}>
                <a href={item.href}>{item.label}</a>
              </li>
            ))}
          </ul>
          <a className="mk-cta" href="#kontakt">
            {nav.cta}
          </a>
        </nav>
      </div>
    </header>
  );
}
