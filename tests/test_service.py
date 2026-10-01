from ctc_reader.models import RegisterDefinition
from ctc_reader.service import probe_range, read_definitions
from ctc_reader.transport import ModbusReadError


class FakeTransport:
    def __init__(self, values: dict[int, int]) -> None:
        self.values = values
        self.calls: list[tuple[int, int]] = []

    def connect(self) -> None:
        pass

    def read_holding_registers(self, address: int, count: int = 1) -> list[int]:
        self.calls.append((address, count))
        try:
            return [self.values[address + offset] for offset in range(count)]
        except KeyError as exc:
            raise ModbusReadError("illegal data address") from exc

    def close(self) -> None:
        pass


def test_read_definitions_continues_after_unsupported_register() -> None:
    transport = FakeTransport({10: 215, 12: 0xFFF6})
    definitions = [
        RegisterDefinition(10, "one", "One", "Test", scale=0.1),
        RegisterDefinition(11, "two", "Two", "Test"),
        RegisterDefinition(12, "three", "Three", "Test", scale=0.1),
    ]

    results = read_definitions(transport, definitions, delay=0, sleep=lambda _: None)

    assert results[0].value == 21.5
    assert not results[1].ok
    assert results[2].value == -1.0
    assert transport.calls == [(10, 1), (11, 1), (12, 1)]


def test_probe_stops_after_consecutive_failures() -> None:
    transport = FakeTransport({1: 10})

    results = probe_range(
        transport,
        1,
        20,
        delay=0,
        max_consecutive_failures=3,
        sleep=lambda _: None,
    )

    assert [address for address, _, _ in results] == [1, 2, 3, 4]


def test_probe_rejects_unbounded_range() -> None:
    transport = FakeTransport({})

    try:
        probe_range(transport, 0, 512, delay=0)
    except ValueError as exc:
        assert "512" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_read_only_transport_protocol_has_no_write_operation() -> None:
    from ctc_reader.transport import PymodbusTcpTransport, ReadOnlyTransport

    assert not hasattr(ReadOnlyTransport, "write_register")
    assert not hasattr(PymodbusTcpTransport, "write_register")



def test_read_definitions_reads_paired_counter_in_one_request() -> None:
    transport = FakeTransport({20: 0x2345, 21: 0x0001})
    definition = RegisterDefinition(
        20,
        "counter",
        "Counter",
        "Test",
        signed=False,
        word_count=2,
        word_order="lsw_first",
    )

    result = read_definitions(transport, [definition], delay=0)[0]

    assert result.raw == (0x2345, 0x0001)
    assert result.value == 0x12345
    assert transport.calls == [(20, 2)]
