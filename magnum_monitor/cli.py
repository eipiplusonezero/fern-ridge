"""Command-line entry point.

Usage:
    python -m magnum_monitor --port /dev/ttyUSB0
    python -m magnum_monitor --port /dev/ttyUSB0 --json
    python -m magnum_monitor --port /dev/ttyUSB0 --json | mosquitto_pub -t magnum -l ...

``--json`` emits one JSON object per line (newline-delimited JSON), which
is the natural handoff point if you want to pipe this into MQTT, InfluxDB,
EmonCMS, or anything else -- decode here, publish elsewhere.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from .decoder import decode_frame
from .framing import iter_frames
from .serial_io import open_magnum_port

logger = logging.getLogger("magnum_monitor")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="magnum-monitor",
        description="Decode data from a Magnum inverter's MagNet RS485 bus.",
    )
    parser.add_argument("--port", required=True, help="Serial device, e.g. /dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=19200, help="Baud rate (default: 19200)")
    parser.add_argument(
        "--json", action="store_true", help="Emit newline-delimited JSON instead of text"
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Stop after decoding this many frames (default: run forever)",
    )
    parser.add_argument("-v", "--verbose", action="count", default=0, help="-v for INFO, -vv for DEBUG")
    return parser


def _configure_logging(verbosity: int) -> None:
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")


def _print_text(frame_dict: dict) -> None:
    inv = frame_dict["inverter"]
    print(
        f"[{inv['model_descr']}] {inv['status_descr']:<18} "
        f"{inv['volts_dc']:5.1f} Vdc  {inv['amps_dc']:5.1f} Adc  "
        f"{inv['volts_ac_out']:3d} Vac-out  fault={inv['fault_descr']}"
    )
    for key, value in frame_dict.items():
        if key == "inverter":
            continue
        print(f"    {key}: {value}")


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)
    _configure_logging(args.verbose)

    count = 0
    try:
        with open_magnum_port(args.port, args.baud) as ser:
            for raw_frame in iter_frames(ser):
                decoded = decode_frame(raw_frame)
                if decoded is None:
                    continue

                frame_dict = decoded.to_dict()
                if args.json:
                    print(json.dumps(frame_dict), flush=True)
                else:
                    _print_text(frame_dict)

                count += 1
                if args.max_frames is not None and count >= args.max_frames:
                    break
    except KeyboardInterrupt:
        logger.info("stopped by user")
        return 0
    except Exception:
        logger.exception("fatal error")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
