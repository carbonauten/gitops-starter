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

## 1. Microsoft 365 (Teams + Outlook)

### Azure App Registration

1. [Entra Admin Center](https://entra.microsoft.com) → **App registrations** → bestehende App (oder neue)
2. **Authentication** → Redirect URI hinzufügen:
   - `https://app.carbonauten.com/api/integrations/microsoft/callback`
3. **API permissions** → Microsoft Graph → **Delegated**:
   - `User.Read`
   - `Team.ReadBasic.All`
   - `Channel.ReadBasic.All`
   - `ChannelMessage.Send`
   - `Mail.ReadWrite`
4. **Grant admin consent** (empfohlen für alle Nutzer)

### Railway Variablen

| Variable | Beschreibung |
|----------|--------------|
| `AZURE_TENANT_ID` | Entra Tenant |
| `AZURE_CLIENT_ID` | App Client ID |
| `AZURE_CLIENT_SECRET` | Client Secret |

### In der App

1. **Mit Microsoft 365 verbinden** klicken
2. Mit IT-Admin-Konto anmelden und Berechtigungen bestätigen
3. **Team** und **Kanal** wählen → **Kanäle speichern**
4. Optional: `PUBLISH_MOCK_MODE=false` setzen für Live-Versand

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
