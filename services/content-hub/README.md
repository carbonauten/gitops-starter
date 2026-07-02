# Unified Carbonauten Platform

Production platform for multilingual content, file, and certificate management with Microsoft Entra ID login.

**Slogan:** FuckCo2 goes international

📋 **Sprint-Roadmap:** [ROADMAP.md](./ROADMAP.md)

## Current status (Sprint 2 ✅)

- Article editor (TipTap) with templates
- Article CRUD (draft / published)
- File upload with folders and download
- Full-text search across articles and files
- Live dashboard statistics
- SQLite locally, PostgreSQL in production via `DATABASE_URL`

## Local development

### Backend

```bash
cd services/content-hub
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
export ENTRA_MOCK_AUTH=true
export SESSION_SECRET=local-dev-secret
export DATABASE_URL=sqlite:///./data/content_hub.db
export UPLOAD_DIR=./data/uploads
uvicorn app.main:app --app-dir backend --reload --port 8080
```

### Frontend dev server

```bash
cd services/content-hub/frontend
npm install
npm run dev
```

Vite proxies `/api` to `http://localhost:8080`.

### Run tests

```bash
cd services/content-hub
pip install -r backend/requirements.txt
pytest -q
```

## Environment variables

| Variable | Description |
|---|---|
| `AZURE_TENANT_ID` | Entra tenant ID |
| `AZURE_CLIENT_ID` | App registration client ID |
| `AZURE_CLIENT_SECRET` | Client secret |
| `REDIRECT_URI` | OAuth callback URL |
| `SESSION_SECRET` | Signed session cookie secret |
| `ENTRA_MOCK_AUTH` | `true` for local dev without Entra |
| `DATABASE_URL` | `sqlite:///./data/content_hub.db` or PostgreSQL URL |
| `UPLOAD_DIR` | Local upload directory (default `./data/uploads`) |
| `MAX_UPLOAD_BYTES` | Upload size limit (default 25 MB) |

Production PostgreSQL example:

```bash
DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/content_hub
```

## Docker

```bash
docker build -t content-hub ./services/content-hub
docker run --rm -p 8080:8080 \
  -e ENTRA_MOCK_AUTH=true \
  -e SESSION_SECRET=local-dev-secret \
  -e DATABASE_URL=sqlite:////app/data/content_hub.db \
  -e UPLOAD_DIR=/app/data/uploads \
  content-hub
```

## Deployment

### Railway (recommended)

See **[DEPLOY-RAILWAY.md](./DEPLOY-RAILWAY.md)** — deploy from GitHub, add PostgreSQL, no server admin.

Quick local stack:

```bash
cd services/content-hub
cp .env.example .env   # edit secrets
docker compose up -d
```

### Kubernetes / Azure (later)

- Image: `ghcr.io/<org>/content-hub:latest`
- Helm chart: `gitops/charts/content-hub`
- Argo CD app: `platform/argocd/content-hub-application.yaml`
- Terraform: `infra/terraform/content-hub.tf`
