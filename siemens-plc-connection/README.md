# Siemens PLC Connection API

Minimal Flask-based HTTP API for reading and writing tags on a Siemens PLC via a pluggable client.

## Endpoints

- `GET /health` — health check
- `GET /plc/config` — exposes current PLC connection config (host, rack, slot)
- `POST /plc/read` — read a tag
  - Body: `{ "address": "DB1.DBW0", "type": "int" }`
- `POST /plc/write` — write a tag
  - Body: `{ "address": "DB1.DBW0", "type": "int", "value": 5 }`

The default `PLCClient` implementation is a stub. Replace `PLCClient.read_tag` and `PLCClient.write_tag`
with a real implementation using e.g. `python-snap7` or an OPC UA client when wiring this up to a live PLC.

## Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
python app.py
```

