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

### Storing data collected from UniLogic

Data sent from the PLC is appended to a **JSONL file** on the computer running the API (one JSON object per line, with UTC timestamp).

- `POST /data/collect` — store data from the PLC. Body: any JSON, e.g. `{ "tag": "Temperature", "value": 23.5 }`. Optional query: `?source=plc`. Returns `201` and the stored record (with `id`, `timestamp_utc`).
- `GET /data/latest?n=100` — read the last N stored records (default 100, max 1000).

**Where it is stored:** by default `data/plc_collected.jsonl` inside the project directory. Override with env var `DATA_FILE=/absolute/path/to/file.jsonl`. The `data/` folder is in `.gitignore` so collected data is not committed.

**Microsoft Azure:** To also store each record in Azure Blob Storage, set in `.env`:
- `AZURE_STORAGE_CONNECTION_STRING` — from Azure Portal → your Storage account → Access keys → Connection string.
- `AZURE_CONTAINER_NAME` — container name (e.g. `plc-data`; create the container in the Portal or it will be created on first write if the account allows).
- `AZURE_BLOB_NAME` (optional) — blob name, default `plc_collected.jsonl`.

Data is appended to an **append blob** in the same JSONL format. If Azure is unreachable, the request still succeeds and data remains in the local file.

**From UniLogic:** add a REST request POST to `http://<API_IP>:8081/data/collect` with JSON body (e.g. your tag names and values). Trigger it from ladder when you want to log a snapshot.

### Snowflake: load from Azure Blob

If Snowflake and Azure Blob are configured, you can load the PLC data (from the same Azure container) into Snowflake.

- `POST /snowflake/load` — creates an external stage (Azure Blob), file format, and table if they don’t exist, then runs `COPY INTO` to load `.jsonl` files from the stage into table `PLC_COLLECTED` (columns: `loaded_at`, `source_filename`, `data` VARIANT). Returns status or error.

**Required env:** `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`, `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`, `SNOWFLAKE_SCHEMA`, `AZURE_STORAGE_ACCOUNT_NAME`, `AZURE_CONTAINER_NAME`, `AZURE_SAS_TOKEN` (SAS token with read/list on the container, from Azure Portal → container → Shared access signature).

## Configuration

- **PLC:** `PLC_HOST` (default 127.0.0.1), `PLC_PORT` (default 502), `PLC_UNIT_ID` (default 1).
- **GitHub:** `GITHUB_TOKEN` or `GITHUB_PAT` — Personal Access Token with required scopes (e.g. `repo`, `workflow` for workflow_dispatch).
- **Data storage:** `DATA_FILE` (optional) — path for collected PLC data, e.g. `/var/data/plc.jsonl`. Default: `data/plc_collected.jsonl` in the project directory.
- **Azure (optional):** `AZURE_STORAGE_CONNECTION_STRING`, `AZURE_CONTAINER_NAME`, `AZURE_BLOB_NAME` (default `plc_collected.jsonl`) — data is also appended to this Azure Blob Storage append blob.
- **Snowflake (optional):** `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`, `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`, `SNOWFLAKE_SCHEMA`; for loading from Azure: `AZURE_STORAGE_ACCOUNT_NAME`, `AZURE_SAS_TOKEN`. Install `snowflake-connector-python`; then `POST /snowflake/load` to load from the Azure stage into Snowflake.

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
