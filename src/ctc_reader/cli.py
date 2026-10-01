from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Sequence

from .decoder import format_value, signed_int16
from .models import ReadResult, RegisterDefinition
from .registry import RegistryError, load_registry
from .service import probe_range, read_definitions
from .transport import ModbusReadError, PymodbusTcpTransport


def _connection_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("host", help="CTC IP address or hostname")
    parser.add_argument("--port", type=int, default=502, help="Modbus TCP port (default: 502)")
    parser.add_argument("--unit-id", type=int, default=1, help="Modbus unit/MB address (default: 1)")
    parser.add_argument("--timeout", type=float, default=2.0, help="request timeout in seconds")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ctc-reader",
        description="Read-only Modbus TCP reader for CTC EcoVent controllers",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    read_parser = subparsers.add_parser("read", help="read the known register catalogue")
    _connection_arguments(read_parser)
    read_parser.add_argument("--register-file", type=Path, help="alternate register JSON file")
    read_parser.add_argument("--only", help="comma-separated register keys")
    read_parser.add_argument("--delay", type=float, default=0.05, help="delay between reads in seconds")
    read_parser.add_argument("--raw", action="store_true", help="show raw register values")
    read_parser.add_argument("--json", action="store_true", help="emit JSON")

    probe_parser = subparsers.add_parser("probe", help="safely probe a bounded address interval")
    _connection_arguments(probe_parser)
    probe_parser.add_argument("--start", type=int, default=62000, help="first zero-based address")
    probe_parser.add_argument("--end", type=int, default=62304, help="last zero-based address")
    probe_parser.add_argument("--delay", type=float, default=0.25, help="delay between reads in seconds")
    probe_parser.add_argument(
        "--max-consecutive-failures",
        type=int,
        default=10,
        help="stop after this many consecutive failed reads",
    )
    probe_parser.add_argument("--show-errors", action="store_true", help="print each failed address")
    probe_parser.add_argument("--json", action="store_true", help="emit JSON")
    return parser


def _validate_connection_args(args: argparse.Namespace) -> None:
    if not 1 <= args.port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    if not 0 <= args.unit_id <= 255:
        raise ValueError("unit ID must be between 0 and 255")
    if args.timeout <= 0:
        raise ValueError("timeout must be greater than zero")
    if args.delay < 0:
        raise ValueError("delay cannot be negative")


def _select_definitions(
    definitions: list[RegisterDefinition], only: str | None
) -> list[RegisterDefinition]:
    if not only:
        return definitions
    requested = {key.strip() for key in only.split(",") if key.strip()}
    known = {definition.key for definition in definitions}
    unknown = requested - known
    if unknown:
        raise ValueError(f"unknown register key(s): {', '.join(sorted(unknown))}")
    return [definition for definition in definitions if definition.key in requested]


def _result_json(result: ReadResult) -> dict[str, object]:
    return {
        "address": result.definition.address,
        "key": result.definition.key,
        "name": result.definition.name,
        "category": result.definition.category,
        "raw": result.raw,
        "value": result.value,
        "unit": result.definition.unit,
        "word_count": result.definition.word_count,
        "uncertain": result.definition.uncertain,
        "note": result.definition.note,
        "error": result.error,
    }


def _print_read_results(
    results: list[ReadResult], *, host: str, port: int, unit_id: int, show_raw: bool
) -> None:
    print(f"CTC at {host}:{port} (unit {unit_id})")
    print(f"Read at {datetime.now().astimezone().isoformat(timespec='seconds')}")

    grouped: dict[str, list[ReadResult]] = defaultdict(list)
    for result in results:
        grouped[result.definition.category].append(result)

    for category, category_results in grouped.items():
        print(f"\n{category}")
        for result in category_results:
            definition = result.definition
            marker = " [?]" if definition.uncertain else ""
            name = f"{definition.name}{marker}"
            if result.ok:
                value = format_value(result.value, definition.unit)  # type: ignore[arg-type]
                raw = f"  [raw={result.raw}]" if show_raw else ""
                print(f"  {definition.address:5d}  {name:<42} {value}{raw}")
            else:
                print(f"  {definition.address:5d}  {name:<42} ERROR: {result.error}")

    successful = sum(result.ok for result in results)
    print(f"\nRead: {successful}  Failed/unsupported: {len(results) - successful}")
    if any(result.definition.uncertain for result in results):
        print("[?] Experimental mapping; use --json to see its validation note.")


def _new_transport(args: argparse.Namespace) -> PymodbusTcpTransport:
    return PymodbusTcpTransport(
        args.host,
        port=args.port,
        unit_id=args.unit_id,
        timeout=args.timeout,
    )


def _run_read(args: argparse.Namespace) -> int:
    definitions = _select_definitions(load_registry(args.register_file), args.only)
    transport = _new_transport(args)
    try:
        transport.connect()
        results = read_definitions(transport, definitions, delay=args.delay)
    finally:
        transport.close()

    if args.json:
        print(json.dumps([_result_json(result) for result in results], indent=2))
    else:
        _print_read_results(
            results,
            host=args.host,
            port=args.port,
            unit_id=args.unit_id,
            show_raw=args.raw,
        )
    return 0 if all(result.ok for result in results) else 1


def _run_probe(args: argparse.Namespace) -> int:
    if args.max_consecutive_failures < 1:
        raise ValueError("max consecutive failures must be at least 1")

    transport = _new_transport(args)
    try:
        transport.connect()
        results = probe_range(
            transport,
            args.start,
            args.end,
            delay=args.delay,
            max_consecutive_failures=args.max_consecutive_failures,
        )
    finally:
        transport.close()

    if args.json:
        print(
            json.dumps(
                [
                    {"address": address, "raw": raw, "error": error}
                    for address, raw, error in results
                ],
                indent=2,
            )
        )
    else:
        print(f"CTC probe at {args.host}:{args.port} (unit {args.unit_id})")
        for address, raw, error in results:
            if error is None and raw is not None:
                print(
                    f"{address:5d}  raw={raw:5d}  hex=0x{raw:04X}  "
                    f"signed={signed_int16(raw):6d}"
                )
            elif args.show_errors:
                print(f"{address:5d}  ERROR: {error}")
        successful = sum(error is None for _, _, error in results)
        print(f"Read: {successful}  Failed/unsupported: {len(results) - successful}")
        if results and results[-1][0] < args.end:
            print("Stopped early after consecutive failures.", file=sys.stderr)

    return 0 if any(error is None for _, _, error in results) else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        _validate_connection_args(args)
        if args.command == "read":
            return _run_read(args)
        return _run_probe(args)
    except (RegistryError, ValueError) as exc:
        parser.error(str(exc))
    except ModbusReadError as exc:
        print(f"Connection/read error: {exc}", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
