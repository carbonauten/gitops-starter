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
| `ENTRA_MOCK_AUTH` | `true` (erster Test) | ✅ |
| `UPLOAD_DIR` | `/app/data/uploads` | ✅ |

**Später für echten M365-Login:**

| Variable | Wert |
|----------|------|
| `ENTRA_MOCK_AUTH` | `false` |
| `AZURE_TENANT_ID` | Entra App Registration |
| `AZURE_CLIENT_ID` | Entra App Registration |
| `AZURE_CLIENT_SECRET` | Entra App Registration |

`REDIRECT_URI` **nicht nötig** — wird automatisch aus `RAILWAY_PUBLIC_DOMAIN` gesetzt.

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

1. `ENTRA_MOCK_AUTH=true` gesetzt?
2. Domain im Browser öffnen
3. **Mit Microsoft anmelden** klicken → Mock-Login als Demo User
4. Dashboard, Artikel, Dateien testen

---

## 8. M365-Login aktivieren (wenn bereit)

1. [Entra Admin](https://entra.microsoft.com) → **App registrations** → **New registration**
2. Redirect URI (Web):

```text
https://DEINE-RAILWAY-DOMAIN.up.railway.app/api/auth/callback
```

3. **Certificates & secrets** → neues Client Secret
4. API permissions: `openid`, `profile`, `email`, `User.Read`
5. Werte in Railway Variables eintragen
6. `ENTRA_MOCK_AUTH` → `false`
7. Redeploy

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
| DB-Verbindung fehlgeschlagen | `DATABASE_URL` Reference von Postgres prüfen |
| Login redirect error | Domain generiert? `RAILWAY_PUBLIC_DOMAIN` wird auto gesetzt |
| Dateien weg nach Deploy | Volume `/app/data/uploads` mounten |
| 502 Bad Gateway | Logs unter **Deployments** → letzter Deploy → **View Logs** |
