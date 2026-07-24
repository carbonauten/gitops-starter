import os
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class PLCConfig:
    host: str
    rack: Optional[int] = None
    slot: Optional[int] = None


class PLCClient:
    """
    Thin abstraction for a Siemens PLC connection.

    This implementation is intentionally minimal and does NOT talk to a real PLC.
    It is designed so that you can later plug in a concrete driver such as:
    - python-snap7 for S7 family PLCs, or
    - an OPC UA client for PLCs exposed via an OPC UA server.
    """

    def __init__(self, config: PLCConfig) -> None:
        self._config = config

    @property
    def config(self) -> PLCConfig:
        return self._config

    def read_tag(self, address: str, data_type: str) -> Any:
        """
        Placeholder read implementation.

        Later, replace the body with real PLC I/O code.
        """
        # For now, just echo back a fake value based on type.
        if data_type.lower() in {"int", "dint"}:
            return 42
        if data_type.lower() in {"bool", "boolean"}:
            return True
        return f"mock-value-for-{address}"

    def write_tag(self, address: str, data_type: str, value: Any) -> None:
        """
        Placeholder write implementation.

        Later, implement real write logic against the PLC.
        """
        # No-op in the stub implementation.
        return None


def load_plc_config_from_env() -> PLCConfig:
    host = os.getenv("PLC_HOST", "127.0.0.1")
    rack = os.getenv("PLC_RACK")
    slot = os.getenv("PLC_SLOT")

    return PLCConfig(
        host=host,
        rack=int(rack) if rack is not None else None,
        slot=int(slot) if slot is not None else None,
    )

