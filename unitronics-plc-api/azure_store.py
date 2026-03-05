"""
Azure Blob Storage (append blob) for data collected from UniLogic/PLC.

If AZURE_STORAGE_CONNECTION_STRING and AZURE_CONTAINER_NAME are set in .env,
each record is appended to a blob (default: plc_collected.jsonl) in that container.
Uses the same JSONL format as the local file (one JSON object per line).
"""

import json
import os
from typing import Any, Dict

try:
    from azure.storage.blob import BlobServiceClient
    from azure.core.exceptions import ResourceExistsError
    _AZURE_AVAILABLE = True
except ImportError:
    _AZURE_AVAILABLE = False

CONTAINER_ENV = "AZURE_CONTAINER_NAME"
CONNECTION_STRING_ENV = "AZURE_STORAGE_CONNECTION_STRING"
BLOB_NAME_ENV = "AZURE_BLOB_NAME"
DEFAULT_BLOB_NAME = "plc_collected.jsonl"


def is_configured() -> bool:
    if not _AZURE_AVAILABLE:
        return False
    conn = os.environ.get(CONNECTION_STRING_ENV, "").strip()
    container = os.environ.get(CONTAINER_ENV, "").strip()
    return bool(conn and container)


def append_line(line: str) -> None:
    """
    Append one line (JSON string + newline) to the Azure append blob.
    Creates the append blob on first write if it does not exist.
    """
    if not _AZURE_AVAILABLE:
        return
    conn = os.environ.get(CONNECTION_STRING_ENV, "").strip()
    container_name = os.environ.get(CONTAINER_ENV, "").strip()
    blob_name = os.environ.get(BLOB_NAME_ENV, "").strip() or DEFAULT_BLOB_NAME
    if not conn or not container_name:
        return

    try:
        service = BlobServiceClient.from_connection_string(conn)
        container = service.get_container_client(container_name)
        blob_client = container.get_blob_client(blob_name)

        # Ensure append blob exists (create only if not exists)
        try:
            blob_client.create_append_blob()
        except ResourceExistsError:
            pass

        data = (line if line.endswith("\n") else line + "\n").encode("utf-8")
        blob_client.append_block(data)
    except Exception:
        raise  # let caller decide whether to ignore
