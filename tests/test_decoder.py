from ctc_reader.decoder import decode_register, signed_int16
from ctc_reader.models import RegisterDefinition


def test_signed_int16_negative() -> None:
    assert signed_int16(0xFFF6) == -10


def test_scaled_negative_temperature() -> None:
    definition = RegisterDefinition(62000, "outdoor", "Outdoor", "Temperature", scale=0.1)
    assert decode_register(0xFFF6, definition) == -1.0


def test_unsigned_value() -> None:
    definition = RegisterDefinition(1, "raw", "Raw", "Test", signed=False)
    assert decode_register(0xFFFF, definition) == 65535


def test_enum_and_unknown_enum() -> None:
    definition = RegisterDefinition(1, "mode", "Mode", "Test", enum={0: "Off", 1: "On"})
    assert decode_register(1, definition) == "On"
    assert decode_register(3, definition) == "Unknown (3)"


def test_unavailable_sentinel_is_not_scaled_as_measurement() -> None:
    definition = RegisterDefinition(
        62003,
        "temperature",
        "Temperature",
        "Test",
        scale=0.1,
        unit="°C",
        unavailable_raw=frozenset({9999}),
    )

    assert decode_register(9999, definition) == "Unavailable"



def test_lsw_first_32_bit_counter() -> None:
    definition = RegisterDefinition(
        62186,
        "total_operation",
        "Total operation",
        "Counters",
        signed=False,
        word_count=2,
        word_order="lsw_first",
    )

    assert decode_register((0x2345, 0x0001), definition) == 0x12345


def test_four_decimal_register_pair() -> None:
    definition = RegisterDefinition(
        62302,
        "price",
        "Price",
        "Electricity price",
        word_count=2,
        encoding="decimal_pair_4",
        unit="SEK/kWh",
    )

    assert decode_register((0, 7689), definition) == 0.7689
    assert decode_register((1, 234), definition) == 1.0234


def test_four_decimal_register_pair_unavailable() -> None:
    definition = RegisterDefinition(
        62302,
        "price",
        "Price",
        "Electricity price",
        word_count=2,
        encoding="decimal_pair_4",
        unavailable_raw=frozenset({32767}),
    )

    assert decode_register((32767, 32767), definition) == "Unavailable"
