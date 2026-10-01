from __future__ import annotations

import time
from collections.abc import Callable, Iterable

from .decoder import decode_register
from .models import ReadResult, RegisterDefinition
from .transport import ModbusReadError, ReadOnlyTransport


def read_definitions(
    transport: ReadOnlyTransport,
    definitions: Iterable[RegisterDefinition],
    *,
    delay: float = 0.05,
    sleep: Callable[[float], None] = time.sleep,
) -> list[ReadResult]:
    results: list[ReadResult] = []
    rows = list(definitions)

    for index, definition in enumerate(rows):
        try:
            words = transport.read_holding_registers(
                definition.address, definition.word_count
            )
            raw: int | tuple[int, ...]
            raw = words[0] if definition.word_count == 1 else tuple(words)
            value = decode_register(raw, definition)
            results.append(ReadResult(definition=definition, raw=raw, value=value))
        except (ModbusReadError, ValueError, IndexError) as exc:
            results.append(ReadResult(definition=definition, error=str(exc)))

        if delay and index < len(rows) - 1:
            sleep(delay)

    return results


def probe_range(
    transport: ReadOnlyTransport,
    start: int,
    end: int,
    *,
    delay: float = 0.25,
    max_consecutive_failures: int = 10,
    sleep: Callable[[float], None] = time.sleep,
) -> list[tuple[int, int | None, str | None]]:
    if not 0 <= start <= end <= 0xFFFF:
        raise ValueError("probe range must satisfy 0 <= start <= end <= 65535")
    if end - start + 1 > 512:
        raise ValueError("probe range is limited to 512 registers per run")

    output: list[tuple[int, int | None, str | None]] = []
    consecutive_failures = 0

    for address in range(start, end + 1):
        try:
            raw = transport.read_holding_registers(address, 1)[0]
            output.append((address, raw, None))
            consecutive_failures = 0
        except (ModbusReadError, ValueError, IndexError) as exc:
            output.append((address, None, str(exc)))
            consecutive_failures += 1
            if consecutive_failures >= max_consecutive_failures:
                break

        if delay and address < end:
            sleep(delay)

    return output
