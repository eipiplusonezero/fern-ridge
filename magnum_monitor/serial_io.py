"""Serial port handling.

Kept deliberately tiny and separate from framing/decoding: this is the
only module that imports ``pyserial``, so the rest of the package (and
its tests) can run without a serial port or the dependency installed.
"""

from __future__ import annotations

import contextlib
import logging

import serial

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def open_magnum_port(port: str, baudrate: int = 19200, read_timeout: float = 0.05):
    """Open the RS485 port used to talk to the Magnum MagNet bus.

    ``read_timeout`` governs how quickly ``read(1)`` gives up when no byte
    has arrived -- this is what lets :mod:`framing` detect gaps between
    bursts without the busy-loop timing trick the original script used.
    """
    ser = serial.Serial(port=port, baudrate=baudrate, bytesize=8, timeout=read_timeout)
    try:
        # Drain whatever was mid-frame when we attached.
        ser.reset_input_buffer()
        logger.info("opened %s @ %d baud", port, baudrate)
        yield ser
    finally:
        ser.close()
        logger.info("closed %s", port)
