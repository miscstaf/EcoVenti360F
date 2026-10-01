from __future__ import annotations

from .models import RegisterDefinition


def signed_int16(raw: int) -> int:
    """Convert an unsigned Modbus word to a signed 16-bit integer."""
    if not 0 <= raw <= 0xFFFF:
        raise ValueError(f"raw register value is outside uint16: {raw}")
    return raw - 0x10000 if raw & 0x8000 else raw


def _validated_words(
    raw: int | tuple[int, ...], definition: RegisterDefinition
) -> tuple[int, ...]:
    words = (raw,) if isinstance(raw, int) else raw
    if len(words) != definition.word_count:
        raise ValueError(
            f"{definition.key} expected {definition.word_count} word(s), got {len(words)}"
        )
    if any(not 0 <= word <= 0xFFFF for word in words):
        raise ValueError("raw register value is outside uint16")
    return words


def _combine_words(words: tuple[int, ...], definition: RegisterDefinition) -> int:
    if len(words) == 1:
        return words[0]
    if definition.word_order == "lsw_first":
        return words[0] | (words[1] << 16)
    return (words[0] << 16) | words[1]


def _decode_decimal_pair_4(words: tuple[int, ...]) -> float:
    integer = signed_int16(words[0])
    fraction = words[1] if words[1] <= 9999 else signed_int16(words[1])
    if abs(fraction) > 9999:
        raise ValueError(f"four-decimal component outside expected range: {fraction}")

    if integer < 0:
        value = integer - abs(fraction) / 10000
    else:
        value = integer + fraction / 10000
    return round(value, 4)


def decode_register(
    raw: int | tuple[int, ...], definition: RegisterDefinition
) -> int | float | str:
    """Decode one scalar or paired Modbus value using a register definition."""
    words = _validated_words(raw, definition)
    if any(word in definition.unavailable_raw for word in words):
        return "Unavailable"
    if definition.encoding == "decimal_pair_4":
        return _decode_decimal_pair_4(words)

    combined = _combine_words(words, definition)
    if definition.word_count == 1:
        base_value = signed_int16(combined) if definition.signed else combined
    elif definition.signed and combined & 0x80000000:
        base_value = combined - 0x100000000
    else:
        base_value = combined

    if definition.enum:
        return definition.enum.get(base_value, f"Unknown ({base_value})")

    value = base_value * definition.scale
    if definition.scale == 1:
        return int(value)
    return round(value, 10)


def format_value(value: int | float | str, unit: str) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, float):
        rendered = f"{value:g}"
    else:
        rendered = str(value)
    return f"{rendered} {unit}" if unit else rendered
