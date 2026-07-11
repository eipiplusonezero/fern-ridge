"""magnum_monitor -- decode a Magnum inverter's MagNet RS485 protocol.

Modernized Python 3 rewrite of obrien28/MagnasineMagPy's magpiV2.py.
See README.md for what changed and why.
"""

from .decoder import DecodedFrame, decode_frame
from . import models

__all__ = ["DecodedFrame", "decode_frame", "models"]

__version__ = "0.1.0"
