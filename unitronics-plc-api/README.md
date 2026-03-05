# Unitronics PLC API

Flask HTTP API for reading and writing tags on Unitronics PLCs (Modbus TCP or vendor protocol), with an optional **GitHub bridge** so the PLC can call GitHub via this API (no token on the PLC).

## Endpoints

### PLC

- `GET /health` — health check
- `GET /plc/config` — current PLC connection config (host, port, unit_id)
- `POST /plc/read` — read a tag (body: `{ "address": "40001", "type": "int" }`)
- `POST /plc/write` — write a tag (body: `{ "address": "40001", "type": "int", "value": 5 }`)

### GitHub bridge (option 2: PLC → this API → GitHub)

Set `GITHUB_TOKEN` (or `GITHUB_PAT`) in the environment. The PLC calls these endpoints; this service calls the GitHub API.

- `GET /github/repos` — list repos for the authenticated user (requires token)
- `GET /github/repo/<owner>/<repo>` — get repo info (e.g. default branch)
- `POST /github/workflow-dispatch` — trigger a `workflow_dispatch` run  
  Body: `{ "owner": "carbonauten", "repo": "gitops-starter", "workflow_id": "terraform-ci.yml", "ref": "main", "inputs": {} }`
- `GET /github/releases/<owner>/<repo>/latest` — latest release (tag_name, name, published_at)

## Configuration

- **PLC:** `PLC_HOST` (default 127.0.0.1), `PLC_PORT` (default 502), `PLC_UNIT_ID` (default 1).
- **GitHub:** `GITHUB_TOKEN` or `GITHUB_PAT` — Personal Access Token with required scopes (e.g. `repo`, `workflow` for workflow_dispatch).

The default `PLCClient` is a stub. Replace `read_tag`/`write_tag` in `plc_client.py` with a real Modbus TCP client (e.g. pymodbus) or vendor SDK for your Unitronics model.

## Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
python app.py
```

## CI

GitHub Actions runs `pytest` on push/PR (see `.github/workflows/ci.yml`).
