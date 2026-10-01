from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any

from .models import RegisterDefinition


class RegistryError(ValueError):
    pass


def _load_document(path: Path | None) -> dict[str, Any]:
    if path is None:
        resource = files("ctc_reader").joinpath("registers.json")
        with resource.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistryError(f"cannot load register file {path}: {exc}") from exc


def load_registry(path: Path | None = None) -> list[RegisterDefinition]:
    document = _load_document(path)
    rows = document.get("registers")
    if not isinstance(rows, list):
        raise RegistryError("register file must contain a 'registers' list")

    definitions: list[RegisterDefinition] = []
    addresses: set[int] = set()
    keys: set[str] = set()

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise RegistryError(f"register entry {index} must be an object")
        try:
            address = int(row["address"])
            key = str(row["key"])
            name = str(row["name"])
            category = str(row["category"])
            signed = row.get("signed", True)
            scale = float(row.get("scale", 1))
            unit = str(row.get("unit", ""))
            note = str(row.get("note", ""))
            word_count = int(row.get("word_count", 1))
            word_order = str(row.get("word_order", "msw_first"))
            encoding = str(row.get("encoding", "scalar"))
            uncertain = row.get("uncertain", False)
            enum_raw = row.get("enum", {})
            unavailable_raw_value = row.get("unavailable_raw", [])
        except (KeyError, TypeError, ValueError) as exc:
            raise RegistryError(f"invalid register entry {index}: {exc}") from exc

        if not 0 <= address <= 0xFFFF:
            raise RegistryError(f"address outside Modbus range: {address}")
        if not isinstance(signed, bool):
            raise RegistryError(f"'signed' must be boolean for {key}")
        if word_count not in {1, 2}:
            raise RegistryError(f"word_count must be 1 or 2 for {key}")
        if address + word_count - 1 > 0xFFFF:
            raise RegistryError(f"register span outside Modbus range for {key}")
        if word_order not in {"msw_first", "lsw_first"}:
            raise RegistryError(f"invalid word_order for {key}: {word_order}")
        if encoding not in {"scalar", "decimal_pair_4"}:
            raise RegistryError(f"invalid encoding for {key}: {encoding}")
        if encoding == "decimal_pair_4" and word_count != 2:
            raise RegistryError(f"decimal_pair_4 requires word_count 2 for {key}")
        if not isinstance(uncertain, bool):
            raise RegistryError(f"'uncertain' must be boolean for {key}")
        occupied = set(range(address, address + word_count))
        overlap = occupied & addresses
        if overlap:
            raise RegistryError(f"duplicate register address: {min(overlap)}")
        if key in keys:
            raise RegistryError(f"duplicate register key: {key}")
        if not isinstance(unavailable_raw_value, list):
            raise RegistryError(f"unavailable_raw must be a list for {key}")
        if not isinstance(enum_raw, dict):
            raise RegistryError(f"'enum' must be an object for {key}")

        try:
            enum = {int(enum_key): str(label) for enum_key, label in enum_raw.items()}
            unavailable_raw = frozenset(int(value) for value in unavailable_raw_value)
        except (TypeError, ValueError) as exc:
            raise RegistryError(f"invalid enum for {key}: {exc}") from exc

        definitions.append(
            RegisterDefinition(
                address=address,
                key=key,
                name=name,
                category=category,
                signed=signed,
                scale=scale,
                unit=unit,
                enum=enum,
                unavailable_raw=unavailable_raw,
                note=note,
                word_count=word_count,
                word_order=word_order,
                encoding=encoding,
                uncertain=uncertain,
            )
        )
        addresses.update(occupied)
        keys.add(key)

    return sorted(definitions, key=lambda item: item.address)
