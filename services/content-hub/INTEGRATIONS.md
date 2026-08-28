# One-Click Integrations — Teams, Outlook, Notion

## Übersicht

Auf **Veröffentlichen → Kanal-Konfiguration** (IT-Master) können Microsoft 365 und Notion per OAuth verbunden werden — ohne manuelle Team-/Kanal-/Datenbank-IDs.

| Kanal | Verbindung | Nach dem Klick |
|-------|------------|----------------|
| **Outlook** | Microsoft 365 OAuth | Automatisch (verbundenes Konto) |
| **Teams** | Microsoft 365 OAuth | Team + Kanal aus Dropdown wählen |
| **Notion** | Notion OAuth | Datenbank aus Dropdown wählen |

> Solange `PUBLISH_MOCK_MODE=true` bleibt, werden nicht konfigurierte Kanäle simuliert. Nach erfolgreicher Verbindung und Auswahl der Ziele werden echte API-Aufrufe genutzt.

---

## 1. Microsoft 365 (Teams + Outlook Publish)

### Azure App Registration

1. [Entra Admin Center](https://entra.microsoft.com) → **App registrations** → bestehende App (oder neue)
2. **Authentication** → Redirect URIs hinzufügen:
   - `https://app.carbonauten.com/api/integrations/microsoft/callback`
   - `https://app.carbonauten.com/api/integrations/outlook/callback`
3. **API permissions** → Microsoft Graph → **Delegated**:
   - `User.Read`
   - `Team.ReadBasic.All`
   - `Channel.ReadBasic.All`
   - `ChannelMessage.Send`
   - `Mail.ReadWrite`
   - `Calendars.ReadWrite` (persönlicher Kalender im Kalender-Tab)
   - `Files.Read` (persönliches OneDrive unter Dateien)
   - `GroupMember.Read.All` (eigene Gruppenmitgliedschaft beim Login, für Entra-Gruppen-Rollen-Mapping)
4. **API permissions** → Microsoft Graph → **Application** (für **M365-Verwaltung**, IT-Master):
   - `User.Read.All`
   - `User.ReadWrite.All`
   - `Directory.Read.All`
   - `Organization.Read.All`
   - `Group.Read.All` (Gruppenliste für den Mapping-Picker)
5. **Grant admin consent** für die Organisation

> Ohne `GroupMember.Read.All`-Consent scheitert nur die Gruppenabfrage beim Login (loggt eine Warnung) — der Login selbst funktioniert trotzdem, nur ohne automatischen Rollen-Sync aus Entra-Gruppen. Siehe [ROADMAP.md](./ROADMAP.md#sprint-o--entra-gruppen-mapping--lizenz-zuweisung--mvp).

### Railway Variablen

| Variable | Beschreibung |
|----------|--------------|
| `AZURE_TENANT_ID` | Entra Tenant |
| `AZURE_CLIENT_ID` | App Client ID |
| `AZURE_CLIENT_SECRET` | Client Secret |

### In der App

**Veröffentlichen (IT-Master):**
1. **Mit Microsoft 365 verbinden** klicken
2. Mit IT-Admin-Konto anmelden und Berechtigungen bestätigen
3. **Team** und **Kanal** wählen → **Kanäle speichern**
4. Optional: `PUBLISH_MOCK_MODE=false` setzen für Live-Versand

**Kalender-Tab / Dateien-Tab (jeder User):**
1. Unter **Kalender** oder **Dateien → OneDrive** → verbinden
2. Mit dem eigenen Microsoft-Konto anmelden
3. Outlook-Termine, E-Mail und OneDrive werden nutzerbezogen freigeschaltet
4. Word/Excel/PowerPoint: unter **Dateien** → **Öffnen** für Office Online Vorschau/Bearbeiten
5. Unabhängig von der IT-Publish-Integration

**M365-Verwaltung (IT-Master):**
1. Application-Berechtigungen wie oben setzen und **Admin Consent** erteilen
2. In der App: **Administration → M365-Verwaltung**
3. Benutzer anlegen, Sign-in sperren, Passwort zurücksetzen
4. Oder Ask Carbonauten: „Welche M365 Benutzer gibt es?“, „Sperre user@carbonauten.com“

Optional: `M365_DIRECTORY_MOCK_MODE=true` zeigt ein Beispielverzeichnis statt Graph.

---

## 2. Notion

### Notion Integration (OAuth)

1. [notion.so/my-integrations](https://www.notion.so/my-integrations) → **New integration**
2. Typ: **Public** (für OAuth)
3. Redirect URI:
   - `https://app.carbonauten.com/api/integrations/notion/callback`
4. Capabilities: **Read content**, **Insert content**, **Update content**

### Railway Variablen

| Variable | Beschreibung |
|----------|--------------|
| `NOTION_CLIENT_ID` | OAuth Client ID |
| `NOTION_CLIENT_SECRET` | OAuth Client Secret |

### In der App

1. **Mit Notion verbinden** klicken
2. Workspace auswählen und Zugriff erlauben
3. **Datenbank** aus Dropdown wählen → **Kanäle speichern**

---

## Troubleshooting

| Problem | Lösung |
|---------|--------|
| Kein „Verbinden“-Button | Env-Variablen in Railway prüfen |
| Microsoft: `integration_token_failed` | Redirect URI exakt wie oben |
| Teams: Nachricht fehlgeschlagen | User muss Team-Mitglied sein; Admin Consent prüfen |
| Notion: leere Datenbank-Liste | Integration in Notion den DBs explizit freigeben |
