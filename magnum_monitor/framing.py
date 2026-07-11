"""Frame boundary detection.

The MagNet bus doesn't use a length prefix or delimiter byte -- the only
way to tell where one frame ends and the next begins is the gap of
silence between bursts. The original script detected this by timing how
long a blocking ``read(1)`` call took and treating "took longer than
30ms" as "we hit a quiet gap, so the next byte starts a new frame". That
works, but it does it with wall-clock timing around a blocking call,
which is fragile (any OS scheduling jitter shifts the threshold) and
hard to unit test.

This version gets the same behaviour from pyserial's built-in read
timeout instead: open the port with ``timeout=read_timeout`` (see
``serial_io.open_magnum_port``), and ``read(1)`` itself returns ``b""``
once that much time has passed with no data. An empty read *is* the
"quiet gap" signal -- no manual timing needed.

If you're building a similar RS485/serial project of your own and you
control the device firmware, prefer a real delimiter or fixed frame
length over gap-timing; it's far more robust than either version of this
approach. Gap-timing is what you reach for when you're stuck reverse-
engineering someone else's protocol, as here.
"""

from __future__ import annotations

import logging
import time
from typing import Iterator

logger = logging.getLogger(__name__)


def iter_frames(ser, settle_time: float = 0.06) -> Iterator[bytes]:
    """Yield raw frames read from an open, timeout-configured serial port.

    ``settle_time`` is how long to wait after the first byte of a new
    burst arrives before grabbing everything sitting in the OS input
    buffer, so we capture the whole burst rather than just its first byte.
    """
    was_idle = True
    while True:
        first_byte = ser.read(1)
        if not first_byte:
            was_idle = True
            continue

        if not was_idle:
            # A byte arrived without a preceding quiet gap -- we're
            # mid-frame from the caller's point of view. Original code
            # only ever sync'd at gap boundaries too, so stray bytes here
            # are dropped rather than mis-framed.
            logger.debug("dropping stray byte outside a gap boundary")
            continue

        time.sleep(settle_time)
        # Only read what's already buffered. Don't fall back to a blocking
        # read(1) here: on a real port that could sit inside its timeout
        # window and pick up the first byte of the *next* burst, silently
        # merging two frames into one.
        waiting = ser.in_waiting
        rest = ser.read(waiting) if waiting else b""
        frame = first_byte + rest
        was_idle = False
        yield frame
