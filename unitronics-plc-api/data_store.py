"""
Simple file-based storage for data collected from UniLogic/PLC.

Uses JSONL (one JSON object per line) so we can append without loading the whole file.
Set DATA_FILE in .env to change path (default: data/plc_collected.jsonl).
If Azure env vars are set, each record is also appended to an Azure Blob Storage append blob.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

try:
    from azure_store import append_line as azure_append_line, is_configured as azure_configured
except ImportError:
    def azure_append_line(_: str) -> None:
        pass
    def azure_configured() -> bool:
        return False

DEFAULT_DATA_DIR = "data"
DEFAULT_FILENAME = "plc_collected.jsonl"


def _get_data_path() -> Path:
    path = os.environ.get("DATA_FILE", "").strip()
    if path:
        return Path(path)
    base = Path(__file__).resolve().parent
    return base / DEFAULT_DATA_DIR / DEFAULT_FILENAME


def _ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def append(payload: Dict[str, Any], source: str = "plc") -> Dict[str, Any]:
    """
    Append one record. Adds timestamp_utc and source.
    Returns the stored record (including id = line number).
    """
    path = _get_data_path()
    _ensure_dir(path)

    record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source": source,
        **payload,
    }

    line = json.dumps(record)
    with open(path, "a") as f:
        f.write(line + "\n")

    if azure_configured():
        try:
            azure_append_line(line)
        except Exception:
            pass  # don't fail the request if Azure is down

    # Approximate id as line count (could open and count)
    with open(path) as f:
        line_count = sum(1 for _ in f)
    record["id"] = line_count
    return record


def read_latest(n: int = 100) -> List[Dict[str, Any]]:
    """Read last n lines (newest last). Returns empty list if file missing."""
    path = _get_data_path()
    if not path.exists():
        return []
    with open(path) as f:
        lines = f.readlines()
    records = []
    for line in lines[-n:] if n else lines:
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records
