"""
Snowflake connection and loading from Azure Blob Storage.

Uses snowflake-connector-python to:
- Connect to Snowflake (env: SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD, etc.)
- Create an external stage pointing at your Azure Blob container (env: AZURE_STORAGE_ACCOUNT_NAME, AZURE_CONTAINER_NAME, AZURE_SAS_TOKEN)
- Create a file format and table for PLC JSONL data
- Run COPY INTO to load from the stage into the table

Prerequisites:
- Snowflake account (any cloud; connector works with all).
- Azure Blob container with the PLC data (same one used by azure_store.py).
- Azure SAS token with read/list on the container (for the stage).
"""

import os
from typing import Any, Dict, List, Optional

try:
    import snowflake.connector
    _SNOWFLAKE_AVAILABLE = True
except ImportError:
    _SNOWFLAKE_AVAILABLE = False

# Env vars
SF_ACCOUNT = "SNOWFLAKE_ACCOUNT"
SF_USER = "SNOWFLAKE_USER"
SF_PASSWORD = "SNOWFLAKE_PASSWORD"
SF_WAREHOUSE = "SNOWFLAKE_WAREHOUSE"
SF_DATABASE = "SNOWFLAKE_DATABASE"
SF_SCHEMA = "SNOWFLAKE_SCHEMA"
SF_ROLE = "SNOWFLAKE_ROLE"  # optional
AZ_ACCOUNT = "AZURE_STORAGE_ACCOUNT_NAME"  # storage account name only, e.g. mystorageaccount
AZ_CONTAINER = "AZURE_CONTAINER_NAME"
AZ_SAS = "AZURE_SAS_TOKEN"  # for Snowflake stage; can be same or different from blob write access
STAGE_NAME = "PLC_AZURE_STAGE"
FILE_FORMAT_NAME = "PLC_JSONL_FORMAT"
TABLE_NAME = "PLC_COLLECTED"


def _getenv(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def is_configured() -> bool:
    """True if Snowflake connector is installed and required env vars are set."""
    if not _SNOWFLAKE_AVAILABLE:
        return False
    return bool(
        _getenv(SF_ACCOUNT)
        and _getenv(SF_USER)
        and _getenv(SF_PASSWORD)
        and _getenv(SF_WAREHOUSE)
        and _getenv(SF_DATABASE)
        and _getenv(SF_SCHEMA)
    )


def get_connection():
    """Return a Snowflake connection (caller must close it)."""
    if not _SNOWFLAKE_AVAILABLE:
        raise RuntimeError("snowflake-connector-python is not installed")
    account = _getenv(SF_ACCOUNT)
    if not account:
        raise ValueError("SNOWFLAKE_ACCOUNT is required")
    # account can be org.account or just account (with optional region)
    conn = snowflake.connector.connect(
        account=account,
        user=_getenv(SF_USER),
        password=_getenv(SF_PASSWORD),
        warehouse=_getenv(SF_WAREHOUSE),
        database=_getenv(SF_DATABASE),
        schema=_getenv(SF_SCHEMA),
        role=_getenv(SF_ROLE) or None,
    )
    return conn


def _stage_url() -> str:
    """Azure blob URL for the stage (container only or container/path)."""
    account = _getenv(AZ_ACCOUNT)
    container = _getenv(AZ_CONTAINER)
    if not account or not container:
        raise ValueError("AZURE_STORAGE_ACCOUNT_NAME and AZURE_CONTAINER_NAME are required for the stage")
    return f"azure://{account}.blob.core.windows.net/{container}/"


def create_stage_if_not_exists(conn) -> None:
    """Create external stage for Azure Blob if it does not exist. Uses AZURE_SAS_TOKEN."""
    sas = _getenv(AZ_SAS)
    if not sas:
        raise ValueError("AZURE_SAS_TOKEN is required to create the Snowflake stage (generate in Azure Portal → container → Shared access signature)")
    url = _stage_url()
    database = _getenv(SF_DATABASE)
    schema = _getenv(SF_SCHEMA)
    sas_escaped = sas.replace("'", "''")
    # Stage without FILE_FORMAT in CREATE (we use it in COPY INTO instead)
    sql = f"""
    CREATE STAGE IF NOT EXISTS {database}.{schema}.{STAGE_NAME}
      URL = '{url}'
      CREDENTIALS = (AZURE_SAS_TOKEN = '{sas_escaped}');
    """
    cur = conn.cursor()
    try:
        cur.execute(sql)
    finally:
        cur.close()


def create_file_format_if_not_exists(conn) -> None:
    """Create JSON file format for JSONL (one JSON object per line)."""
    database = _getenv(SF_DATABASE)
    schema = _getenv(SF_SCHEMA)
    sql = f"""
    CREATE FILE FORMAT IF NOT EXISTS {database}.{schema}.{FILE_FORMAT_NAME}
      TYPE = JSON
      COMPRESSION = AUTO
      STRIP_OUTER_ARRAY = FALSE;
    """
    cur = conn.cursor()
    try:
        cur.execute(sql)
    finally:
        cur.close()


def create_plc_table_if_not_exists(conn) -> None:
    """Create table for PLC collected records (one VARIANT column for the JSON line)."""
    database = _getenv(SF_DATABASE)
    schema = _getenv(SF_SCHEMA)
    sql = f"""
    CREATE TABLE IF NOT EXISTS {database}.{schema}.{TABLE_NAME} (
      loaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
      source_filename VARCHAR,
      data VARIANT
    );
    """
    cur = conn.cursor()
    try:
        cur.execute(sql)
    finally:
        cur.close()


def copy_into_plc_table(conn, pattern: str = ".*\\.jsonl") -> Dict[str, Any]:
    """
    Run COPY INTO to load from the Azure stage into PLC_COLLECTED.
    pattern: regex for files to load, default all .jsonl files.
    Returns summary dict with rows_loaded, etc.
    """
    database = _getenv(SF_DATABASE)
    schema = _getenv(SF_SCHEMA)
    # COPY INTO with single VARIANT column; $1 is the whole row (one JSON object per line)
    sql = f"""
    COPY INTO {database}.{schema}.{TABLE_NAME} (source_filename, data)
      FROM (
        SELECT METADATA$FILENAME, $1
        FROM @{database}.{schema}.{STAGE_NAME}
      )
      PATTERN = '{pattern}'
      FILE_FORMAT = {database}.{schema}.{FILE_FORMAT_NAME}
      ON_ERROR = CONTINUE;
    """
    cur = conn.cursor()
    try:
        cur.execute(sql)
        row = cur.fetchone()
        # COPY returns rows_unloaded, rows_loaded, etc.
        return {"status": "success", "message": row}
    finally:
        cur.close()


def setup_and_load() -> Dict[str, Any]:
    """
    One-shot: create file format, table, stage (if not exist), then run COPY INTO.
    Returns a summary. Call with Snowflake and Azure env vars set.
    """
    if not is_configured():
        return {"error": "snowflake_not_configured", "message": "Set SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD, SNOWFLAKE_WAREHOUSE, SNOWFLAKE_DATABASE, SNOWFLAKE_SCHEMA"}
    conn = get_connection()
    try:
        create_file_format_if_not_exists(conn)
        create_plc_table_if_not_exists(conn)
        create_stage_if_not_exists(conn)
        result = copy_into_plc_table(conn)
        return result
    finally:
        conn.close()
