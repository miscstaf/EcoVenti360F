from __future__ import annotations

from typing import Protocol


class ModbusReadError(RuntimeError):
    pass


class ReadOnlyTransport(Protocol):
    def connect(self) -> None: ...

    def read_holding_registers(self, address: int, count: int = 1) -> list[int]: ...

    def close(self) -> None: ...


class PymodbusTcpTransport:
    """Narrow FC03-only adapter around PyModbus.

    No write operation is exposed by this class.
    """

    def __init__(
        self,
        host: str,
        *,
        port: int = 502,
        unit_id: int = 1,
        timeout: float = 2.0,
    ) -> None:
        from pymodbus.client import ModbusTcpClient

        self.host = host
        self.port = port
        self.unit_id = unit_id
        self._client = ModbusTcpClient(host=host, port=port, timeout=timeout, retries=0)

    def connect(self) -> None:
        if not self._client.connect():
            raise ModbusReadError(f"could not connect to {self.host}:{self.port}")

    def read_holding_registers(self, address: int, count: int = 1) -> list[int]:
        if not 0 <= address <= 0xFFFF:
            raise ValueError(f"address outside Modbus range: {address}")
        if not 1 <= count <= 100:
            raise ValueError(f"count must be between 1 and CTC's limit of 100: {count}")

        try:
            response = self._client.read_holding_registers(
                address,
                count=count,
                device_id=self.unit_id,
            )
        except Exception as exc:
            raise ModbusReadError(f"read {address} failed: {exc}") from exc

        if response.isError():
            raise ModbusReadError(f"read {address} returned {response}")
        registers = getattr(response, "registers", None)
        if not isinstance(registers, list) or len(registers) != count:
            raise ModbusReadError(
                f"read {address} returned {len(registers) if isinstance(registers, list) else 0} "
                f"registers; expected {count}"
            )
        return [int(value) for value in registers]

    def close(self) -> None:
        self._client.close()
