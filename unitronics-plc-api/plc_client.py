import os
from dataclasses import dataclass
from typing import Any, Optional, Tuple

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException


@dataclass
class PLCConfig:
    host: str
    port: int = 502  # Modbus TCP default
    unit_id: Optional[int] = 1  # Modbus slave/unit ID


def _parse_address(address: str) -> Tuple[str, int]:
    """
    Parse Modbus address string into (kind, 0-based address).
    - "40001" -> ("holding", 0), "40002" -> ("holding", 1)
    - "0", "00001", "1" -> ("coil", 0) or ("coil", 1) for 1-based
    """
    s = address.strip()
    if not s:
        raise ValueError("Empty address")
    if not s.isdigit():
        raise ValueError(f"Invalid address: {address}")
    num = int(s)
    if num >= 40000:
        return "holding", num - 40001
    return "coil", num if num < 10000 else num - 1


class PLCClient:
    """
    Modbus TCP client for Unitronics PLCs.

    Connects lazily on first read/write. Uses PLC_HOST, PLC_PORT, PLC_UNIT_ID.
    Addresses: holding registers 40001-49999 (e.g. 40001 = register 0),
    coils 0-9999 (0-based).
    """

    def __init__(self, config: PLCConfig) -> None:
        self._config = config
        self._client: Optional[ModbusTcpClient] = None

    @property
    def config(self) -> PLCConfig:
        return self._config

    def _get_client(self) -> ModbusTcpClient:
        if self._client is None:
            self._client = ModbusTcpClient(
                host=self._config.host,
                port=self._config.port,
            )
        return self._client

    def _ensure_connected(self) -> bool:
        client = self._get_client()
        if not client.connected:
            return client.connect()
        return True

    def read_tag(self, address: str, data_type: str) -> Any:
        unit_id = self._config.unit_id or 1
        kind, addr = _parse_address(address)
        if not self._ensure_connected():
            raise ConnectionError(f"Could not connect to {self._config.host}:{self._config.port}")

        client = self._get_client()
        if kind == "coil":
            result = client.read_coils(addr, count=1, slave=unit_id)
            if result.isError():
                raise ModbusException(str(result))
            return bool(result.bits[0]) if result.bits else False

        # holding register(s)
        if data_type.lower() in {"dint", "double", "float"}:
            count = 2
        else:
            count = 1
        result = client.read_holding_registers(addr, count=count, slave=unit_id)
        if result.isError():
            raise ModbusException(str(result))
        regs = result.registers
        if not regs:
            return 0
        if data_type.lower() in {"bool", "boolean"}:
            return bool(regs[0])
        if data_type.lower() in {"dint", "double"} and len(regs) >= 2:
            return (regs[0] << 16) | regs[1]
        return regs[0]

    def write_tag(self, address: str, data_type: str, value: Any) -> None:
        unit_id = self._config.unit_id or 1
        kind, addr = _parse_address(address)
        if not self._ensure_connected():
            raise ConnectionError(f"Could not connect to {self._config.host}:{self._config.port}")

        client = self._get_client()
        if kind == "coil":
            result = client.write_coil(addr, bool(value), slave=unit_id)
        else:
            if data_type.lower() in {"bool", "boolean"}:
                value = 1 if value else 0
            result = client.write_register(addr, int(value), slave=unit_id)
        if result.isError():
            raise ModbusException(str(result))

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None


def load_plc_config_from_env() -> PLCConfig:
    host = os.getenv("PLC_HOST", "127.0.0.1")
    port_s = os.getenv("PLC_PORT", "502")
    unit_s = os.getenv("PLC_UNIT_ID", "1")
    try:
        port = int(port_s)
    except ValueError:
        port = 502
    try:
        unit_id = int(unit_s)
    except ValueError:
        unit_id = 1
    return PLCConfig(host=host, port=port, unit_id=unit_id)
