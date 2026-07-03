# Railway Deployment — Unified Carbonauten Platform

Kostenloser Start zum Testen auf Railway.

## Checkliste (ca. 15 Minuten)

- [ ] 1. Repo auf GitHub pushen
- [ ] 2. Railway-Projekt erstellen
- [ ] 3. PostgreSQL hinzufügen
- [ ] 4. Umgebungsvariablen setzen
- [ ] 5. Volume für Datei-Uploads
- [ ] 6. Öffentliche Domain generieren
- [ ] 7. Testen mit Mock-Login

---

## 1. Repo auf GitHub pushen

Railway deployt aus GitHub. Das Repo muss dort liegen (z. B. `carbonauten/gitops-starter`).

---

## 2. Railway-Projekt erstellen

1. Öffne [railway.app](https://railway.app) → **Login with GitHub**
2. **New Project** → **Deploy from GitHub repo**
3. Repository auswählen
4. **Settings → Build:**
   - **Builder:** Dockerfile
   - **Dockerfile Path:** `/services/content-hub/Dockerfile`

5. Optional: **Settings → Source → Root Directory:** `services/content-hub`

> Das Dockerfile funktioniert auch **ohne** Root Directory (Monorepo-Pfad ist eingebaut).

---

## 3. PostgreSQL hinzufügen

1. Im Projekt: **+ New** → **Database** → **PostgreSQL**
2. Warten bis Postgres läuft (grüner Status)
3. **content-hub** Service → **Variables** → **+ New Variable** → **Add Reference**
4. Postgres-Service wählen → Variable **`DATABASE_URL`** verknüpfen

Die App wandelt `postgres://` automatisch für SQLAlchemy um.

---

## 4. Umgebungsvariablen

**content-hub** → **Variables** → diese Werte setzen:

| Variable | Wert | Pflicht |
|----------|------|---------|
| `SESSION_SECRET` | z. B. `openssl rand -hex 32` | ✅ |
| `ENTRA_MOCK_AUTH` | `false` | ✅ |
| `UPLOAD_DIR` | `/app/data/uploads` | ✅ |
| `IT_ADMIN_EMAILS` | z. B. `mike.mueller@carbonauten.com` | ✅ |
| `INITIAL_ADMIN_EMAIL` | dieselbe E-Mail wie IT-Admin | ✅ |
| `INITIAL_ADMIN_PASSWORD` | sicheres Startpasswort (min. 8 Zeichen) | ✅ |
| `INITIAL_ADMIN_NAME` | optional, z. B. `Mike Mueller` | optional |

**Login:** E-Mail + Passwort auf `/login` (kein Auto-Login mehr).

**Microsoft SSO (später optional):**

| Variable | Wert |
|----------|------|
| `ENTRA_MOCK_AUTH` | `false` |
| `AZURE_TENANT_ID` | Entra App Registration |
| `AZURE_CLIENT_ID` | Entra App Registration |
| `AZURE_CLIENT_SECRET` | Entra App Registration |
| `IT_ADMIN_EMAILS` | z. B. `it@carbonauten.com,admin@carbonauten.com` |
| `DEFAULT_USER_ROLE` | `editor` (Standard für neue Mitarbeiter) |
| `REDIRECT_URI` | `https://app.carbonauten.com/api/auth/callback` (bei Custom Domain) |

`IT_ADMIN_EMAILS` erhält **immer** die Master-Rolle (`it_master`).

Prüfen ob die Variable aktiv ist: `https://app.carbonauten.com/api/health` → `"it_admin_configured": true`

Prüfen: `https://app.carbonauten.com/api/health` → `"password_auth": true`, `"bootstrap_admin_configured": true`

> `INITIAL_ADMIN_PASSWORD` wird bei jedem Deploy für `INITIAL_ADMIN_EMAIL` synchronisiert (Passwort-Reset). Nach dem ersten Login kann die Variable in Railway entfernt werden.

**E-Mail-Einladungen (Mitarbeiterverwaltung → Tab „Einladungen“):**

> **Wichtig:** Railway **Hobby/Free blockiert SMTP** (Port 587). Nutze **Resend** (HTTPS-API) — das ist der empfohlene Weg.

| Variable | Wert | Pflicht |
|----------|------|---------|
| `APP_PUBLIC_URL` | z. B. `https://app.carbonauten.com` | ✅ (für korrekten Einladungslink) |
| `RESEND_API_KEY` | API-Key von [resend.com](https://resend.com) | ✅ (empfohlen auf Railway) |
| `SMTP_FROM_EMAIL` | z. B. `noreply@carbonauten.com` (Domain in Resend verifizieren) | ✅ |
| `SMTP_FROM_NAME` | z. B. `Carbonauten Platform` | optional |
| `INVITE_EXPIRY_DAYS` | `7` (Standard) | optional |

**Resend einrichten (5 Min):**
1. Account auf [resend.com](https://resend.com) anlegen
2. Domain `carbonauten.com` hinzufügen → DNS-Einträge setzen (SPF, DKIM)
3. API Key erstellen → als `RESEND_API_KEY` in Railway
4. `SMTP_FROM_EMAIL` = verifizierte Absender-Adresse (z. B. `noreply@carbonauten.com`)
5. Redeploy → `/api/health` sollte `"email_provider": "resend"` zeigen

**SMTP (nur Railway Pro oder anderer Host):**

| Variable | Wert |
|----------|------|
| `SMTP_HOST` | z. B. `smtp.office365.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` / `SMTP_PASSWORD` | Postfach-Zugangsdaten |

Ohne E-Mail-Konfiguration wird die Einladung trotzdem erstellt; der Link erscheint in der Admin-Oberfläche zum manuellen Teilen. Prüfen: `/api/health` → `"email_delivery_configured": true`

`DATABASE_URL` kommt aus Schritt 3 (Reference).

---

## 5. Volume für Datei-Uploads

Ohne Volume gehen hochgeladene Dateien bei jedem Redeploy verloren.

1. **content-hub** → **Settings** → **Volumes**
2. **Add Volume**
3. Mount Path: `/app/data/uploads`
4. Redeploy auslösen

---

## 6. Öffentliche Domain

1. **content-hub** → **Settings** → **Networking**
2. **Generate Domain**
3. URL notieren, z. B. `content-hub-production-a1b2.up.railway.app`
4. Im Browser öffnen: `https://content-hub-production-a1b2.up.railway.app`

Health-Check: `https://DEINE-DOMAIN/api/health` → sollte `{"status":"ok"}` zurückgeben.

---

## 7. Erster Test

1. `ENTRA_MOCK_AUTH=false` und Initial-Admin-Variablen gesetzt?
2. Domain öffnen → `/login`
3. Mit `INITIAL_ADMIN_EMAIL` + `INITIAL_ADMIN_PASSWORD` anmelden
4. Oben rechts sollte **IT-Master** stehen
5. Dashboard, Mitarbeiterverwaltung und Abteilungen testen

---

## 8. Microsoft SSO aktivieren

E-Mail/Passwort und Microsoft-Login funktionieren **parallel**. Bestehende Konten werden per E-Mail verknüpft.

### 8.1 Entra App Registration

1. [Entra Admin](https://entra.microsoft.com) → **App registrations** → **New registration**
2. Name: `Unified Carbonauten Platform`
3. Supported account types: **Single tenant** (nur eure Organisation)
4. Redirect URI (Web):

```text
https://app.carbonauten.com/api/auth/callback
```

5. **Register** klicken und notieren:
   - **Application (client) ID**
   - **Directory (tenant) ID**

### 8.2 Client Secret

1. App → **Certificates & secrets** → **New client secret**
2. Secret-Wert kopieren (wird nur einmal angezeigt)

### 8.3 API Permissions

1. App → **API permissions** → **Add a permission** → **Microsoft Graph** → **Delegated**
2. Hinzufügen: `openid`, `profile`, `email`, `User.Read`
3. Optional: **Grant admin consent** für die Organisation

### 8.4 Railway Variables (zusätzlich)

| Variable | Wert |
|----------|------|
| `AZURE_TENANT_ID` | Directory (tenant) ID |
| `AZURE_CLIENT_ID` | Application (client) ID |
| `AZURE_CLIENT_SECRET` | Client Secret |
| `APP_PUBLIC_URL` | `https://app.carbonauten.com` |
| `ENTRA_MOCK_AUTH` | `false` |
| `IT_ADMIN_EMAILS` | `mike.mueller@carbonauten.com` |

> `APP_PUBLIC_URL` ist wichtig bei Custom Domain. Die Redirect-URI wird daraus automatisch gebildet.

Alternativ statt `APP_PUBLIC_URL`:

```text
REDIRECT_URI=https://app.carbonauten.com/api/auth/callback
```

### 8.5 Testen

1. Redeploy abwarten
2. `https://app.carbonauten.com/api/health` prüfen:
   - `"microsoft_auth": true`
   - `"sso_redirect_uri": "https://app.carbonauten.com/api/auth/callback"`
3. `/login` öffnen → **Mit Microsoft anmelden**
4. Mit M365-Konto anmelden
5. IT-Master-E-Mails erhalten automatisch die Master-Rolle

Beim ersten Microsoft-Login wird das Konto **automatisch angelegt** (Self-Service). Existiert bereits ein Konto mit derselben E-Mail (Passwort-Login), wird es **verknüpft** — Passwort-Login bleibt optional nutzbar.

---

## 9. Multichannel-Veröffentlichung (Sprint 4)

Unter `/publish` können veröffentlichte Artikel an **Teams**, **Outlook** und **Notion** gesendet werden.

### Mock-Modus (Standard ohne Graph/Notion)

| Variable | Wert |
|----------|------|
| `PUBLISH_MOCK_MODE` | `true` |

Kanäle werden simuliert — gut zum Testen der UI und Historie.

### Produktion (Microsoft Graph + Notion)

**Graph Application Permissions** (Admin Consent):

| Permission | Zweck |
|------------|-------|
| `ChannelMessage.Send` | Teams-Kanal-Nachrichten |
| `Mail.ReadWrite` | Outlook-Entwürfe |

| Variable | Wert |
|----------|------|
| `PUBLISH_MOCK_MODE` | `false` |
| `AZURE_TENANT_ID` / `AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET` | wie SSO |
| `TEAMS_TEAM_ID` | Teams Team-ID |
| `TEAMS_CHANNEL_ID` | Teams Kanal-ID |
| `OUTLOOK_SENDER_ID` | User-ID oder E-Mail des Absenders |
| `NOTION_API_KEY` | Notion Integration Token |
| `NOTION_DATABASE_ID` | Notion Datenbank-ID |

Kanäle können zusätzlich in der App unter **Veröffentlichen** (IT-Master) konfiguriert werden.

`/api/health` zeigt: `publish_mock_mode`, `graph_publish_configured`, `notion_configured`

---

## 10. Dateien: SharePoint + OneDrive

Unter `/files` gibt es drei Quellen: **Plattform**, **SharePoint**, **OneDrive**.

### Mock-Modus (Standard)

| Variable | Wert |
|----------|------|
| `FILES_BROWSE_MOCK_MODE` | `true` |

Zeigt Beispiel-Ordner für SharePoint/OneDrive zum UI-Test.

### Produktion

**Graph Application Permissions** (zusätzlich zu Publish):

| Permission | Zweck |
|------------|-------|
| `Files.Read.All` | SharePoint + OneDrive lesen |

| Variable | Wert |
|----------|------|
| `FILES_BROWSE_MOCK_MODE` | `false` |
| `SHAREPOINT_SITE_URL` | z. B. `https://carbonauten.sharepoint.com/sites/Firmendokumente` |
| `SHAREPOINT_DISPLAY_NAME` | `Firmendokumente` |
| `SHAREPOINT_DRIVE_ID` | optional, falls mehrere Libraries |
| `AZURE_*` | wie SSO |

OneDrive zeigt das Laufwerk des **aktuell angemeldeten Users** (E-Mail aus Session).

`/api/health` → `sharepoint_configured`, `files_browse_mock_mode`

---

## 11. China-Sync (Sprint 5, EU-Seite)

Für den Datenaustausch mit der China-Instanz auf der **EU**-Railway-App:

| Variable | Beispiel | Zweck |
|----------|----------|-------|
| `DEPLOYMENT_REGION` | `eu` | Regionskennung |
| `STORAGE_BACKEND` | `local` | Dateispeicher (EU: lokal/Volume) |
| `SYNC_PEER_URL` | `https://platform.cn.carbonauten.com` | China-Instanz |
| `SYNC_PEER_REGION` | `cn` | Partner-Region |
| `SYNC_API_KEY` | gemeinsames Geheimnis | Sync-Auth (gleicher Wert in CN) |

IT-Master: **Dashboard** → **Regionalsync** → manuell starten.

Details: [DEPLOY-CHINA.md](./DEPLOY-CHINA.md)

`/api/health` → `deployment_region`, `sync_configured`, `sync_peer_region`

---

## 12. Workflow & Audit (Sprint 6)

Artikel-Freigabe und Audit-Log sind ohne Extra-Konfiguration aktiv.

- Redakteure: Entwurf → **Zur Prüfung einreichen**
- IT-Master: **Freigaben** (`/workflow`) — sofort oder mit Termin veröffentlichen
- Zertifikatserneuerung: Freigabe durch IT-Master oder Rolle `certificate_manager`
- Audit-Log: `/audit` (nur IT-Master)

Siehe [WORKFLOW.md](./WORKFLOW.md) und `GET /api/monitor/summary` für IT-Monitoring.

---

## Kosten

| Phase | Kosten |
|-------|--------|
| Trial / neues Konto | oft ~$5 Guthaben |
| Leichte interne Nutzung | ~$0–5/Monat |
| Tägliche Team-Nutzung | ~$10–20/Monat |

**Tipp:** In Railway → **Usage** den Verbrauch im Blick behalten.

---

## Updates deployen

Push auf `main` (Pfad `services/content-hub/**`) → Railway baut automatisch neu.

Oder manuell: Service → **Deployments** → **Redeploy**.

---

## Troubleshooting

| Problem | Lösung |
|---------|--------|
| Build schlägt fehl | Root Directory = `services/content-hub` prüfen |
| DB-Verbindung fehlgeschlagen | Postgres-Service läuft? `DATABASE_URL` als **Reference** vom Postgres-Service verknüpfen (nicht leer lassen) |
| Login redirect error | Domain generiert? `RAILWAY_PUBLIC_DOMAIN` wird auto gesetzt |
| Dateien weg nach Deploy | Volume `/app/data/uploads` mounten |
| 502 Bad Gateway | Logs unter **Deployments** → letzter Deploy → **View Logs** |
