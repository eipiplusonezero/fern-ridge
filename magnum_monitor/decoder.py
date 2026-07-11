"""Top-level frame decoder.

A single serial "frame" from the MagNet bus contains an inverter status
block (always present), a remote base block, and then a device-specific
detail block identified by a footer marker byte at offset 42. Several
detail blocks are themselves chained pairs -- e.g. a "Remote A0" block is
always immediately followed by an "AGS1" block, per the sample captures
in the original script's header comment:

    Remote_B+A0+A1   footer(42)=0xA0  -> RemoteA0 (36-42) + AGS1  (43-48)
    Remote_B+A1+A2   footer(42)=0xA1  -> RemoteA1 (36-42) + AGS2  (43-48)
    Remote_B+A2+RTR  footer(42)=0xA2  -> RemoteA2 (36-42) + RTR   (43-44)
    Remote_B+A3      footer(42)=0xA3  -> RemoteA3 (36-42), no pair
    Remote_B+A4      footer(42)=0xA4  -> RemoteA4 (36-42), no pair
    Remote_B+Z0      footer(42)=0x00  -> RemoteZ0 (36-42), no pair
    Remote_B+80+81   footer(42)=0x80  -> RemoteBMK(36-42) + BMK   (43-60)

The original code only ever dispatched on the *first* block and never
decoded the second half of these pairs (the AGS1/AGS2/RTR/BMK classes
existed but ``mainLoop`` never called them). This decoder fixes that by
decoding both halves whenever the frame is long enough to contain them.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from . import models

logger = logging.getLogger(__name__)

MIN_FRAME_LEN = 23  # inverter block only, no remote attached
FOOTER_OFFSET = 42  # byte position of the primary detail-type marker

# footer byte -> (name, decoder, min length, paired-name, paired decoder, paired min length)
_DETAIL_TABLE: dict[int, tuple] = {
    0xA0: ("remote_a0", models.RemoteA0.decode, 43, "ags1", models.AGS1.decode, 49),
    0xA1: ("remote_a1", models.RemoteA1.decode, 43, "ags2", models.AGS2.decode, 49),
    0xA2: ("remote_a2", models.RemoteA2.decode, 43, "rtr", models.RTR.decode, 45),
    0xA3: ("remote_a3", models.RemoteA3.decode, 43, None, None, None),
    0xA4: ("remote_a4", models.RemoteA4.decode, 43, None, None, None),
    0x00: ("remote_z0", models.RemoteZ0.decode, 43, None, None, None),
    0x80: ("remote_bmk", models.RemoteBMK.decode, 43, "bmk", models.BMK.decode, 61),
}


@dataclass(frozen=True)
class DecodedFrame:
    inverter: models.InverterStatus
    remote_base: Optional[models.RemoteBase] = None
    details: Optional[dict] = None  # e.g. {"remote_a0": RemoteA0(...), "ags1": AGS1(...)}

    def to_dict(self) -> dict:
        out = {"inverter": models.to_dict(self.inverter)}
        if self.remote_base is not None:
            out["remote_base"] = models.to_dict(self.remote_base)
        for name, obj in (self.details or {}).items():
            out[name] = models.to_dict(obj)
        return out


def decode_frame(buf: bytes) -> Optional[DecodedFrame]:
    """Decode one raw frame. Returns None if the frame is too short to
    contain even the base inverter block (caller should treat that as a
    dropped/partial read and move on, not crash).
    """
    if len(buf) < MIN_FRAME_LEN:
        logger.debug("frame too short (%d bytes), dropping", len(buf))
        return None

    inverter = models.InverterStatus.decode(buf)

    if len(buf) <= MIN_FRAME_LEN:
        return DecodedFrame(inverter=inverter)

    remote_base = models.RemoteBase.decode(buf, inverter.system_bus_volts)

    details: dict = {}
    if len(buf) > FOOTER_OFFSET:
        footer = buf[FOOTER_OFFSET]
        entry = _DETAIL_TABLE.get(footer)
        if entry is None:
            logger.debug("unrecognised footer marker 0x%02x", footer)
        else:
            name, decode_fn, min_len, pair_name, pair_decode_fn, pair_min_len = entry
            if len(buf) >= min_len:
                details[name] = decode_fn(buf, inverter.system_bus_volts)
            if pair_name and len(buf) >= pair_min_len:
                details[pair_name] = pair_decode_fn(buf, inverter.system_bus_volts)

    return DecodedFrame(inverter=inverter, remote_base=remote_base, details=details)
