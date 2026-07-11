# magnum_monitor

A modernized Python 3 rewrite of [obrien28/MagnasineMagPy](https://github.com/obrien28/MagnasineMagPy)'s
`magpiV2.py`, which decodes the RS485 "MagNet" protocol used by Magnum
inverters (MS-series, ME-series, etc.) to talk to their remote panel,
AGS generator-start controller, and battery monitor.

## Hardware

You need something to convert between the Magnum inverter's RS485 output
and whatever your monitoring device speaks — a Raspberry Pi (any model;
this is 19200 baud, a Pi Zero W is plenty) works well and is what the
original project targeted.

**Adapter.** The simplest option is a USB-to-RS485 adapter/dongle (~$10–15,
common chipsets are FTDI, CH340, CP2102). Plug it into any Pi USB port and
it shows up as `/dev/ttyUSB0` (or similar) — that's what you pass to
`--port`. The alternative is an RS485 HAT on the Pi's GPIO header (a
MAX485-style chip); more wiring, but frees up the USB port and is a better
fit for a permanent/enclosed build.

**Wiring.** The inverter's green "Network" RJ11 jack (per the pinout
documented in the original project, since Magnum's own comms-protocol PDF
was out of date for at least one inverter model):

- Pin 2 = A+ (0–5V)
- Pin 3 = GND
- Pin 5 = B− (7–12V)
- Pins 1, 4 = not connected; pin 6 (14V) not needed for data

Connect A/B/GND to the matching terminals on the RS485 adapter.

**Permissions.** Your user account may not have access to the serial
device by default:

```bash
sudo usermod -a -G dialout $USER
```

then log out/in (or reboot) for it to take effect.

**First run.** Once wired up, run with verbose logging to see whether
frames are actually syncing — this is the real test of whether the
framing/decode logic (see "Honest caveats" below) holds up against real
hardware, which I have not been able to verify against a live inverter:

```bash
python -m magnum_monitor --port /dev/ttyUSB0 --json -v
```

## Why this needed a rewrite, not just a cleanup

The original is Python 2 and **cannot run as-is on Python 3**: it decodes
every byte with `ord(packet_buffer[i])`. In Python 2, indexing a `str`
gives you a one-character string, so `ord()` converts it to an int. In
Python 3, indexing a `bytes` object *already* gives you an `int`, and
`ord()` raises `TypeError: ord() expected a character, but string of
length 0 found` (or similar) the first time it's called. That's almost
certainly the "I don't know if it's working" you're seeing — it can't be
working, on any current Python install.

Beyond that, the structure fights maintainability:

- **Global mutable state.** `system_bus_volts` is a module-level global
  written by the inverter decoder and read by nine other decoders. Any
  test, reorder, or concurrent use has to reason about *when* that global
  gets set relative to when it's read.
- **Long `if`/`if`/`if` chains** (not even `elif`) mapping codes to
  descriptions — e.g. ~20 sequential ifs just for fault codes. Easy to
  typo, hard to skim, and adding one more code means finding the right
  spot in a wall of near-identical lines.
- **Class attributes doing double duty as instance state**, with no
  `__init__`. It happens to work for scalars, but it's the kind of
  pattern that bites you the moment a field is a list or dict.
- **Two never-decoded packet types.** The `AGS1`/`AGS2`/`RTR`/`BMK`
  classes exist but `mainLoop()`'s dispatch never calls them — despite
  the sample captures in the file's own header comment showing they
  arrive chained behind `A0`/`A1`/`A2`/BMK-remote frames. This rewrite
  decodes both halves of each pair.
- **Frame sync via wall-clock timing around a blocking read**, which
  works but is fragile and effectively impossible to unit test.

## What changed

| Area | Original | Here |
|---|---|---|
| Byte access | `ord(packet_buffer[i])` | `buf[i]` (already an `int` in Python 3) |
| Code → description | ~20-line `if` chains per field | `dict` lookup tables in `constants.py` |
| Shared state | `global system_bus_volts` | passed as an explicit argument |
| Packet representation | bare classes, no `__init__` | frozen `dataclass`es, one per packet type |
| Protocol dispatch | `if/elif` in `mainLoop()`, two packet types silently unreachable | table-driven dispatch in `decoder.py`, decodes chained pairs |
| Frame sync | timed blocking reads in a hand-rolled loop | pyserial's built-in read timeout (`framing.py`) |
| Output | `print` statements mixed into the decode loop | decoding returns data; `cli.py` formats it separately, with a `--json` mode |
| Tests | none | `tests/`, runnable without hardware or a serial port |

## Layout

```
magnum_monitor/
  constants.py   lookup tables (status/fault/model codes, etc.)
  models.py      one frozen dataclass + decode() per packet type
  decoder.py     stitches a raw frame into inverter + remote_base + details
  framing.py     splits the continuous byte stream into frames
  serial_io.py   the only module that imports pyserial
  cli.py         argparse entry point, text or --json output
tests/           unit tests for constants/models/decoder/framing
```

## Usage

```bash
pip install -r requirements.txt
python -m magnum_monitor --port /dev/ttyUSB0
python -m magnum_monitor --port /dev/ttyUSB0 --json    # newline-delimited JSON
```

`--json` is the intended hook for MQTT/InfluxDB/EmonCMS/whatever: decode
here, pipe the JSON lines to whatever publishes it. That keeps this
package's only job as "turn bytes into structured data."

## Honest caveats

- **I could not test this against real Magnum hardware** — I only have
  the original script's source and its header-comment sample captures to
  work from, not a live inverter. The byte offsets and scaling factors
  are carried over from the original as faithfully as I could read them,
  and the included tests check the *arithmetic* (dict lookups, bit
  masking, scaling by bus voltage) against hand-built byte buffers, not
  against a real capture. Before trusting values off your own inverter,
  compare a few readings against what Magnum's own remote panel reports.
- A couple of spots in the original were themselves ambiguous or
  arguably buggy (e.g. `battery_low_trip` uses the same scale for 12V and
  24V systems but doubles it for 48V — reproduced as-is since I can't
  confirm which behavior is intentional without a real system to test
  against).
- If this is a template for **your own** RS485/serial project and you
  have any control over the far end's protocol, don't reach for
  gap-timing frame sync (`framing.py`'s approach) — use a real length
  prefix or delimiter byte. Gap-timing is what you do when you're stuck
  reverse-engineering someone else's undocumented protocol, as here.
