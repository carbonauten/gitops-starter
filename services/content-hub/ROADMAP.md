# Unified Carbonauten Platform — Sprint Roadmap

**Slogan:** FuckCo2 goes international

Produktions-Roadmap für die interne Multichannel-Plattform: Artikel, Dateien und **Zertifikate** zentral verwalten und an Microsoft 365 (Outlook, Teams) sowie Notion verteilen — nutzbar für technische und nicht-technische Mitarbeiter in Europa und China.

---

## Vision

Eine selbsterklärende Web-Plattform, auf der Teams Inhalte und Zertifikate einmal erfassen und gezielt an mehrere Kanäle veröffentlichen — mit Microsoft-Login, dreisprachiger Oberfläche (DE / EN / 中文) und kostengünstigem Betrieb über GitHub + Azure/Alibaba.

```mermaid
flowchart LR
    subgraph Sprint1["✅ Sprint 1"]
        Auth[Entra ID Login]
        I18n[DE / EN / 中文]
        Nav[Navigation]
    end

    subgraph Sprint2["Sprint 2"]
        Editor[Artikel-Editor]
        Files[Datei-Upload]
    end

    subgraph Sprint3["Sprint 3"]
        Certs[Zertifikatsverwaltung]
        Reminders[Ablauf-Erinnerungen]
    end

    subgraph Sprint4["Sprint 4"]
        Teams[Teams]
        Notion[Notion]
        Outlook[Outlook]
    end

    subgraph Sprint5["Sprint 5"]
        China[China Deployment]
        Sync[EU ↔ China Sync]
    end

    subgraph Sprint6["Sprint 6"]
        Workflow[Freigabe-Workflow]
        Audit[Audit & Monitoring]
    end

    Sprint1 --> Sprint2 --> Sprint3 --> Sprint4 --> Sprint5 --> Sprint6
```

---

## Sprint-Übersicht

| Sprint | Dauer | Status | Ziel |
|--------|-------|--------|------|
| 1 | 2 Wochen | ✅ Abgeschlossen | Fundament: Login, Branding, Mehrsprachigkeit, CI/CD |
| 2 | 2 Wochen | ✅ Abgeschlossen | Redaktion: Artikel-Editor, Dateiverwaltung, Suche |
| 3 | 2 Wochen | 🔜 Nächster | **Zertifikatsverwaltung:** Erfassung, Ablauf, Erinnerungen |
| 4 | 2 Wochen | Geplant | Multichannel: Teams, Notion, Outlook |
| 5 | 2 Wochen | Geplant | China: Alibaba-Deployment, Datensync EU ↔ CN |
| 6 | 1 Woche | Geplant | Workflow, Freigaben, Audit, Go-Live |
| 7+ | laufend | Backlog | Erweiterungen (siehe unten) |

---

## Sprint 1 — Fundament ✅

**Ziel:** Mitarbeiter können sich anmelden und die Plattform in ihrer Sprache nutzen.

### Deliverables

- [x] Projektstruktur `services/content-hub/`
- [x] FastAPI-Backend mit Entra-ID-Login (Mock-Modus für Dev)
- [x] React-Frontend mit Language Switch: `de`, `en`, `zh-CN`
- [x] Branding: Logo, **Unified Carbonauten Platform**, Slogan
- [x] Dashboard, Artikel, Dateien, **Zertifikate**, Veröffentlichen (Navigation)
- [x] GitHub Actions → GHCR
- [x] Helm Chart + Argo CD Manifest
- [x] Terraform-Scaffold Azure Container Apps
- [x] Tests (Backend)

### Akzeptanzkriterien

- Login mit Microsoft (oder Mock in Dev)
- UI vollständig in drei Sprachen umschaltbar
- CI baut und testet bei jedem Push
- Docker-Image lauffähig

---

## Sprint 2 — Redaktion & Dateien ✅

**Ziel:** Mitarbeiter können Artikel schreiben und Dateien hochladen — ohne technisches Know-how.

### Deliverables

- [x] WYSIWYG-Artikel-Editor (TipTap)
- [x] Artikel-CRUD: Erstellen, Bearbeiten, Löschen, Entwurf / Veröffentlicht
- [x] Vorlagen: Wochenbericht, Ankündigung, Protokoll
- [x] Datei-Upload per Drag & Drop
- [x] Ordnerstruktur (general, compliance, marketing)
- [x] Volltextsuche über Artikel und Dateinamen
- [x] SQLite/PostgreSQL via SQLAlchemy (`DATABASE_URL`)
- [x] Lokaler Dateispeicher (`UPLOAD_DIR`)
- [x] API-Tests

### Akzeptanzkriterien

- Redakteur erstellt Artikel mit Formatierung (fett, Listen, Links)
- Dateien werden hochgeladen und sind wieder auffindbar
- Suche liefert relevante Treffer in < 2 Sekunden
- Alle UI-Texte in DE / EN / 中文

### Technik

```
backend/app/models/article.py
backend/app/models/file.py
backend/app/routes/articles.py
backend/app/routes/files.py
frontend/src/pages/ArticleEditor.tsx
frontend/src/pages/FilesPage.tsx (erweitert)
```

---

## Sprint 3 — Zertifikatsverwaltung

**Ziel:** Alle relevanten Zertifikate an einem Ort — mit Ablaufüberwachung und automatischen Erinnerungen.

### Zertifikat-Typen

| Kategorie | Beispiele | Typische Nutzer |
|-----------|-----------|-----------------|
| Compliance & ISO | ISO 9001, ISO 14001, Audit-Berichte | Qualität, Management |
| Produktzertifikate | CE, REACH, Materialprüfungen | Produktion, Vertrieb |
| Schulungen & Personal | Erste-Hilfe, Gabelstapler, Sicherheit | HR, Teamleiter |
| SSL / Infrastruktur | TLS-Zertifikate, Domain-Certs | IT / DevOps |

### Geplante Features

- [ ] Zertifikat anlegen: Name, Kategorie, Aussteller, Gültig von/bis
- [ ] PDF/Datei-Upload pro Zertifikat (verknüpft mit Datei-Speicher aus Sprint 2)
- [ ] Dashboard-Widget: „Läuft in 30/60/90 Tagen ab“
- [ ] Ampel-Status: gültig / läuft ab / abgelaufen
- [ ] Verantwortliche Person + Entra-Benutzer zuweisen
- [ ] Erinnerungen per **Outlook** (E-Mail) und **Teams** (Nachricht)
- [ ] Erneuerungs-Workflow: abgelaufen → in Bearbeitung → erneuert
- [ ] Filter & Suche nach Kategorie, Status, Aussteller
- [ ] Export-Liste (CSV/PDF) für Audits
- [ ] Optional: SSL-Zertifikat-Import (.pem / .crt) mit automatischer Ablauf-Erkennung

### Akzeptanzkriterien

- Nicht-technischer Nutzer legt ein ISO-Zertifikat in < 3 Minuten an
- 30-Tage-Erinnerung wird automatisch an Verantwortlichen gesendet
- Dashboard zeigt alle ablaufenden Zertifikate auf einen Blick
- Audit-Export enthält alle Pflichtfelder
- UI vollständig in DE / EN / 中文

### Technik

```
backend/app/models/certificate.py
backend/app/routes/certificates.py
backend/app/workers/cert_expiry_reminder.py
frontend/src/pages/CertificatesPage.tsx (erweitert)
frontend/src/pages/CertificateDetail.tsx
frontend/src/components/CertificateForm.tsx
```

### Architektur Erinnerungen

```mermaid
flowchart LR
    Cron[Täglicher Job] --> Check[Ablauf prüfen]
    Check -->|30/60/90 Tage| Notify[Benachrichtigung]
    Notify --> Outlook[Outlook E-Mail]
    Notify --> Teams[Teams Nachricht]
    Notify --> Dashboard[Dashboard Badge]
```

---

## Sprint 4 — Multichannel-Veröffentlichung

**Ziel:** Ein Klick — Inhalt erscheint in Teams, Notion und als Outlook-Entwurf. Zertifikat-Erinnerungen nutzen dieselbe Graph-Anbindung.

### Geplante Features

- [ ] Microsoft Graph: Teams-Kanal-Nachrichten senden
- [ ] Microsoft Graph: Outlook-Entwurf / E-Mail mit Anhang
- [ ] Notion API: Seite in Datenbank anlegen / aktualisieren
- [ ] Veröffentlichen-Dialog mit Kanal-Checkboxen (Artikel)
- [ ] Zertifikat-Benachrichtigungen über Graph (aus Sprint 3)
- [ ] Status pro Kanal: ✓ gesendet / ⏳ wartet / ✗ Fehler
- [ ] Automatischer Retry bei API-Fehlern
- [ ] Veröffentlichungs-Historie pro Artikel
- [ ] Admin: Kanäle konfigurieren (Teams-Team, Notion-DB, etc.)

### Akzeptanzkriterien

- Artikel wird an mindestens 2 von 3 Zielen erfolgreich gesendet
- Zertifikat-Ablauf-Erinnerung kommt per Outlook und Teams an
- Fehlgeschlagene Syncs sind sichtbar und manuell wiederholbar

### Berechtigungen (Entra / Graph)

| Permission | Zweck |
|------------|-------|
| `ChannelMessage.Send` | Teams-Nachrichten |
| `Mail.Send` / `Mail.ReadWrite` | Outlook-Erinnerungen |
| `Files.ReadWrite` | Anhänge via OneDrive/SharePoint |
| Notion Integration Token | Seiten + Dateien |

---

## Sprint 5 — China-Deployment

**Ziel:** Mitarbeiter in China arbeiten mit akzeptabler Latenz — inkl. Zertifikatsdaten.

### Geplante Features

- [ ] Deployment auf Alibaba ECS (China-Region)
- [ ] Alibaba OSS für Dateispeicher in China
- [ ] Regionale URL: z. B. `platform.cn.carbonauten.com`
- [ ] Kafka MirrorMaker 2: Artikel + Zertifikate + Metadaten EU ↔ China
- [ ] Load Balancer / Geo-Routing (EU vs. CN)
- [ ] 21Vianet M365-Anbindung (falls China-Tenant)
- [ ] Performance-Tests aus China (Latenz < 3s Seitenaufbau)
- [ ] Terraform-Erweiterung Alibaba ECS + OSS

### Akzeptanzkriterien

- China-Nutzer erreichen Plattform ohne VPN
- Zertifikate und Artikel syncen EU ↔ CN innerhalb definierter Zeit
- Dateien liegen regional (EU in Azure Blob, CN in OSS)

---

## Sprint 6 — Workflow & Go-Live

**Ziel:** Produktionsreifer Betrieb mit Freigaben und Nachvollziehbarkeit.

### Geplante Features

- [ ] Freigabe-Workflow: Entwurf → Review → Veröffentlichen (Artikel + Zertifikate)
- [ ] Rollen: Admin, Redakteur, Zertifikats-Manager, Leser (Entra-Gruppen)
- [ ] Termin-Veröffentlichung (scheduled publish)
- [ ] Audit-Log: Wer hat wann was geändert / veröffentlicht
- [ ] Onboarding-Hilfe in der UI (Tooltips, Kurzanleitung pro Sprache)
- [ ] Produktions-Deployment EU
- [ ] Monitoring (Health, Fehlerrate, Sync-Status, Zertifikat-Abläufe)
- [ ] Dokumentation für Admins und Redakteure

### Akzeptanzkriterien

- Zertifikat-Erneuerung erfordert Freigabe durch definierte Rolle
- Vollständiges Audit für Compliance-Anfragen
- 10+ Pilotnutzer arbeiten 1 Woche produktiv

---

## Backlog (Sprint 7+)

| Thema | Beschreibung | Priorität |
|-------|--------------|-----------|
| Zertifikat-Ketten | Abhängigkeiten zwischen Zertifikaten (Parent/Child) | Hoch |
| Auto-Import CA | Let's Encrypt / Azure Key Vault Sync | Mittel |
| Versionierung | Artikel- und Zertifikat-Historie, Diff | Hoch |
| KI-Assistenz | Zusammenfassung, Übersetzung DE↔EN↔中文 | Mittel |
| SharePoint | Zertifikate aus SharePoint-Bibliothek importieren | Mittel |
| Mobile | Responsive Optimierung / PWA | Niedrig |
| Analytics | Veröffentlichungs- und Zertifikat-Statistiken | Niedrig |

---

## Kosten-Richtwerte (monatlich)

### Phase 1 — Railway Start (empfohlen jetzt)

| Posten | Lösung | Kosten |
|--------|--------|--------|
| App-Hosting | Railway | Trial / ~$5–15/Monat |
| Datenbank | Railway PostgreSQL | inkl. / günstig |
| CI/CD + Registry | GitHub + GHCR | €0 |
| **Gesamt** | | **~$0–15/Monat** |

Siehe [DEPLOY-RAILWAY.md](./DEPLOY-RAILWAY.md).

### Später — Multi-Cloud

| Posten | EU | China | Summe |
|--------|-----|-------|-------|
| App-Hosting | Azure Container Apps | Alibaba ECS | ~15–25 € |
| Datenbank | Neon/Azure | RDS | ~5–17 € |
| Dateispeicher | Azure Blob | OSS | ~2–6 € |
| CI/CD + Registry | 0 € (GitHub) | — | 0 € |
| M365 + Notion APIs | 0 € (bestehende Lizenzen) | 0 € | 0 € |
| **Gesamt** | | | **~15–40 €/Monat** |

---

## Team & Rollen

| Rolle | Verantwortung |
|-------|---------------|
| Product Owner | Prioritäten, Akzeptanz, Pilotnutzer |
| Dev / GitOps | Implementierung, CI/CD, Terraform |
| Admin Entra/M365 | App Registration, Berechtigungen |
| Admin Notion | Integration, Datenbank-Schema |
| Zertifikats-Manager | Kategorien, Verantwortliche, Audit-Anforderungen |
| China IT | Alibaba-Zugang, 21Vianet ggf. |
| Pilot-Redakteure | Feedback nach jedem Sprint |

---

## Definition of Done (alle Sprints)

- [ ] Code im Repo, PR reviewed
- [ ] Tests grün (CI)
- [ ] UI-Texte in DE / EN / 中文
- [ ] README / Roadmap aktualisiert
- [ ] Keine Secrets im Code
- [ ] Demo für Stakeholder möglich

---

## Nächster Schritt

**Sprint 3 starten:** Zertifikatsverwaltung mit Ablaufüberwachung und Erinnerungen.

Siehe auch: [README.md](./README.md) für lokale Entwicklung und Deployment.
