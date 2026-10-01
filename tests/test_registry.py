import json
from pathlib import Path

import pytest

from ctc_reader.registry import RegistryError, load_registry


def test_bundled_registry_is_valid_and_sorted() -> None:
    definitions = load_registry()
    assert definitions
    assert definitions[0].address == 62000
    assert len({definition.address for definition in definitions}) == len(definitions)
    assert len({definition.key for definition in definitions}) == len(definitions)


def test_duplicate_addresses_are_rejected(tmp_path: Path) -> None:
    document = {
        "registers": [
            {"address": 1, "key": "one", "name": "One", "category": "Test"},
            {"address": 1, "key": "two", "name": "Two", "category": "Test"},
        ]
    }
    path = tmp_path / "registers.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(RegistryError, match="duplicate register address"):
        load_registry(path)



def test_overlapping_multiword_registers_are_rejected(tmp_path: Path) -> None:
    document = {
        "registers": [
            {
                "address": 1,
                "key": "counter",
                "name": "Counter",
                "category": "Test",
                "word_count": 2,
            },
            {"address": 2, "key": "two", "name": "Two", "category": "Test"},
        ]
    }
    path = tmp_path / "registers.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(RegistryError, match="duplicate register address: 2"):
        load_registry(path)
