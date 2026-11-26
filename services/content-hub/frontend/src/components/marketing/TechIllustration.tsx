/** Decorative placeholder line illustration for the technology section. */
export function TechIllustration() {
  return (
    <svg
      className="mk-tech-illustration"
      viewBox="0 0 220 220"
      role="img"
      aria-label="Schematische Darstellung des Verfahrens"
      focusable="false"
    >
      <g fill="none" stroke="#fff" strokeWidth="2" opacity="0.9">
        <ellipse cx="110" cy="60" rx="55" ry="14" />
        <path d="M55 60 V140 a55 14 0 0 0 110 0 V60" />
        <path d="M80 100 h60" />
        <path d="M70 120 h80" />
      </g>
    </svg>
  );
}
