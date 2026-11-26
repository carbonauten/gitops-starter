import { Link } from "react-router-dom";

import wortmarkeZusatzWeiss from "../../assets/elphen/wortmarke-zusatz-weiss.png";
import { footer } from "../../content/marketingSite";

export function MarketingFooter() {
  return (
    <footer className="mk-footer">
      <div className="mk-footer-inner">
        <div>
          <img src={wortmarkeZusatzWeiss} alt={footer.companyName} style={{ height: 32, marginBottom: "0.75rem" }} />
          <div>
            {footer.addressLines.map((line) => (
              <div key={line}>{line}</div>
            ))}
          </div>
        </div>
        <div>
          <div>Kontakt</div>
          <div>
            <a href={`mailto:${footer.contactEmail}`}>{footer.contactEmail}</a>
          </div>
          <div>{footer.phone}</div>
        </div>
        <ul className="mk-footer-links">
          {footer.links.map((item) => (
            <li key={item.href}>
              <Link to={item.href}>{item.label}</Link>
            </li>
          ))}
        </ul>
      </div>
    </footer>
  );
}
