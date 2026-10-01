# CTC EcoVent Modbus reader

A deliberately read-only Python command-line application for inspecting a CTC EcoVent i360F over Modbus TCP.

The application exposes only Modbus function code 3 (Read Holding Registers). It does not implement register, coil, or combined read/write operations.

## Before running it

On the CTC display:

1. Open `Advanced / Define / Remote control` (`Avancerat / Definiera / Fjärrstyrning`).
2. Set `Ethernet` to `Modbus TCP`.
3. Open `Advanced / Settings / Communication / BMS`.
4. Confirm the TCP port (normally `502`) and MB address/unit ID (normally `1`).

Keep port 502 on the trusted local network. Do not expose it through router port forwarding.

## Install

Python 3.10 or newer is required.

```console
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

## Read the known catalogue

```console
ctc-reader read 192.168.1.50
```

Useful options:

```console
ctc-reader read 192.168.1.50 --port 502 --unit-id 1 --timeout 2
ctc-reader read 192.168.1.50 --only outdoor_temperature,primary_flow_temperature
ctc-reader read 192.168.1.50 --raw
ctc-reader read 192.168.1.50 --json
```

The bundled catalogue is based on CTC BMS manual `162 600 16-1`, dated 2023-09-26. That document explicitly lists the EcoVent i350F/controller family rather than the i360F. Treat every entry as a candidate until its value has been compared with the i360F display.

## Probe a documented address interval

The CTC read-only data block currently documented in the bundled source starts at register 62000. Probe a small interval first:

```console
ctc-reader probe 192.168.1.50 --start 62000 --end 62020
```

The probe:

- sends only FC03 requests;
- reads one register per request so an unsupported address cannot hide adjacent values;
- waits between requests;
- stops after repeated transport failures;
- refuses ranges larger than 512 registers.

Use several bounded runs instead of scanning the entire 0–65535 address space.

## Interpreting results

A successful Modbus response means that the address can be read; it does not prove that an undocumented value has the meaning inferred from another CTC model. Validate temperatures and modes against the physical display and record the installed controller software version.

Signed temperatures are converted from 16-bit two's-complement and then multiplied by the documented scale. Live i360F validation showed raw `9999` for several unavailable measurements; the catalogue renders those confirmed cases as `Unavailable`. Use `--raw` or `probe` when validating scaling, sentinels, and address offsets.

## Experimental mappings

Terminal entries marked [?] are experimental. Their uncertainty and validation evidence are stored in the register note and included by ctc-reader read --json. Paired 32-bit operating-time counters are read in one request; --raw displays both source words. Electricity-price registers 62302-62303 are combined into one SEK/kWh value.

## Tests

```console
pytest
```

Tests use fake transports and never contact the heating controller.

## Sources

- CTC BMS manual `162 600 16-1`, 2023-09-26.
- [CTC EcoVent/i360-family installation manual](https://ctc.se/file-download-product/5529.pdf)
- [Modbus Application Protocol V1.1b3](https://www.modbus.org/file/secure/modbusprotocolspecification.pdf)
- [PyModbus documentation](https://pymodbus.readthedocs.io/)

See [ACCESS_CODES.md](ACCESS_CODES.md) for the separately documented protected-menu reference and its safety warnings.
