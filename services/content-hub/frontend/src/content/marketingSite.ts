/**
 * Placeholder copy for the public elphen marketing site (home + legal pages).
 *
 * Everything in here is DRAFT content written to match the look of the elphen
 * design mockup, not verified company fact. Before this goes live, replace:
 *   - every `[...]` bracketed placeholder below (legal address, register
 *     number, VAT ID, bank details)
 *   - the product/project copy with real offerings and case studies
 *   - the "Über elphen" text with an approved company description
 *
 * This is the single file to edit for that - nothing else in the marketing
 * site hardcodes copy.
 */

export const nav = {
  brandTagline: "regenerative products and ecosystems",
  links: [
    { label: "Über", href: "#ueber" },
    { label: "Produkte", href: "#produkte" },
    { label: "Technologie", href: "#technologie" },
    { label: "Projekte", href: "#projekte" },
  ],
  cta: "Kontakt aufnehmen",
};

export const hero = {
  headline: "Green Tech industriell skalieren",
};

export const about = {
  heading: "Über elphen AG",
  // DRAFT - replace with an approved company description.
  paragraph:
    "elphen entwickelt regenerative Produkte und Kreislauf-Ökosysteme für die Industrie: aus " +
    "Reststoffen und Biomasse entstehen Werkstoffe, Energie und neue Wertschöpfungsketten, die " +
    "fossile Rohstoffe ersetzen. Wir verbinden Verfahrenstechnik, Chemie und Projektentwicklung, " +
    "um Kreislaufwirtschaft industriell nutzbar zu machen.",
  worldwideHeading: "weltweit tätig",
  // DRAFT - replace with real locations/markets once confirmed.
  worldwideParagraph:
    "Mit Projekten und Partnerinnen in Europa, Nordamerika und Asien bringen wir regenerative " +
    "Produktionsverfahren dorthin, wo Reststoffe anfallen und Industrien sie brauchen.",
};

export type ProductCategory = {
  title: string;
  description: string;
};

// DRAFT category names/descriptions - replace with the real product portfolio.
export const products: ProductCategory[] = [
  {
    title: "Kunststoffe & Compounds",
    description: "Biobasierte und kreislauffähige Compounds als Ersatz für fossile Kunststoffe.",
  },
  {
    title: "Biomasse",
    description: "Aufbereitung und Veredelung von Rest- und Biomasseströmen zu Industrierohstoffen.",
  },
  {
    title: "Lederersatz",
    description: "Pflanzenbasierte Materialien als regenerative Alternative zu Leder.",
  },
  {
    title: "Chemie",
    description: "Grundstoffe und Spezialchemikalien aus regenerativen Prozessen.",
  },
  {
    title: "Lebensmittelwirtschaft",
    description: "Verwertung von Reststoffen aus der Lebensmittelproduktion in neue Produktlinien.",
  },
  {
    title: "Energie",
    description: "Energetische Nutzung von Reststoffen entlang der Kreislaufkette.",
  },
];

export const technology = {
  heading: "Technologie",
  // DRAFT - replace with the real process description.
  paragraph:
    "Unsere Verfahren verarbeiten Rest- und Biomasseströme in industriellem Maßstab zu " +
    "stabilen, zertifizierbaren Produkten - von der Rohstoffannahme bis zur Qualitätssicherung " +
    "in der Linie.",
};

export type Project = {
  title: string;
  description: string;
};

// DRAFT project placeholders - replace with real case studies once approved for publication.
export const projects: Project[] = [
  {
    title: "Projekt A",
    description: "[Kurzbeschreibung eines realen Referenzprojekts einfügen.]",
  },
  {
    title: "Projekt B",
    description: "[Kurzbeschreibung eines realen Referenzprojekts einfügen.]",
  },
];

export const contact = {
  heading: "Aktie anfragen",
  nameLabel: "Name",
  emailLabel: "E-Mail-Adresse",
  messageLabel: "Nachricht",
  submit: "Anfrage senden",
};

export const footer = {
  companyName: "Elphen AG",
  // DRAFT - replace with the real registered address.
  addressLines: ["[Straße Nr.]", "[PLZ Ort]"],
  // DRAFT - replace with a real monitored inbox before publishing.
  contactEmail: "info@elphen.ag",
  // DRAFT - replace with the real phone number.
  phone: "[Telefonnummer]",
  links: [
    { label: "Impressum", href: "/impressum" },
    { label: "Datenschutz", href: "/datenschutz" },
  ],
};

export const impressum = {
  title: "Impressum",
  sections: [
    {
      heading: "Angaben gemäß § 5 TMG",
      // DRAFT - every bracketed value must be confirmed before publishing.
      lines: [
        "Elphen AG",
        "[Straße Nr.]",
        "[PLZ Ort]",
        "",
        "Handelsregister: [Registergericht, HRB-Nummer]",
        "Vertreten durch: [Name des Vorstands/der Geschäftsführung]",
        "",
        "Kontakt:",
        "E-Mail: info@elphen.ag",
        "Telefon: [Telefonnummer]",
        "",
        "Umsatzsteuer-ID gemäß § 27a UStG: [USt-IdNr.]",
      ],
    },
    {
      heading: "Verantwortlich für den Inhalt nach § 18 Abs. 2 MStV",
      lines: ["[Name, Anschrift wie oben]"],
    },
    {
      heading: "Streitschlichtung",
      lines: [
        "Die Europäische Kommission stellt eine Plattform zur Online-Streitbeilegung (OS) " +
          "bereit: https://ec.europa.eu/consumers/odr/. Wir sind zur Teilnahme an einem " +
          "Streitbeilegungsverfahren vor einer Verbraucherschlichtungsstelle [nicht/zur Teilnahme " +
          "bereit] - Angabe vor Veröffentlichung prüfen.",
      ],
    },
  ],
};

export const datenschutz = {
  title: "Datenschutz",
  sections: [
    {
      heading: "1. Verantwortlicher",
      lines: ["Elphen AG, [Straße Nr.], [PLZ Ort], info@elphen.ag"],
    },
    {
      heading: "2. Erhebung und Verarbeitung personenbezogener Daten",
      lines: [
        "[DRAFT - hier die tatsächlich erhobenen Daten beschreiben, z. B. Kontaktformular, " +
          "Server-Logs, Cookies/Tracking-Tools. Dieser Platzhaltertext ersetzt keine " +
          "rechtliche Prüfung durch einen Datenschutzbeauftragten.]",
      ],
    },
    {
      heading: "3. Ihre Rechte",
      lines: [
        "Sie haben das Recht auf Auskunft, Berichtigung, Löschung, Einschränkung der " +
          "Verarbeitung, Datenübertragbarkeit und Widerspruch gemäß Art. 15-21 DSGVO. Wenden " +
          "Sie sich dazu an info@elphen.ag.",
      ],
    },
    {
      heading: "4. Kontakt Datenschutzbeauftragter",
      lines: ["[Falls vorhanden: Name und Kontaktdaten des Datenschutzbeauftragten einfügen.]"],
    },
  ],
};
