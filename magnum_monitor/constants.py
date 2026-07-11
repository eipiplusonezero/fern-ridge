"""Lookup tables for the Magnum MagNet protocol.

These replace the long chains of ``if self.x == '0x..': self.y = "..."``
in the original script. A dict lookup is O(1), self-documenting, and
trivial to extend when Magnum documents (or you reverse-engineer) a new
code -- you add one line instead of hunting through a wall of ifs.
"""

from __future__ import annotations

INVERTER_STATUS = {
    0x00: "Charger Standby",
    0x01: "Equalizing",
    0x02: "Float Charging",
    0x04: "Absorb Charging",
    0x08: "Bulk Charging",
    0x09: "Battery Saver",
    0x10: "Charge",
    0x20: "Off",
    0x40: "Inverting",
    0x50: "Standby",
    0x60: "Searching",
}

INVERTER_FAULT = {
    0x00: "No Faults",
    0x01: "Stuck Relay",
    0x02: "DC Overload",
    0x03: "AC Overload",
    0x04: "Dead Battery",
    0x05: "AC Backfeed",
    0x08: "Low Battery Cutout",
    0x09: "High Battery Cutout",
    0x0A: "High AC Output Volts",
    0x10: "Bad FET Bridge",
    0x12: "FETs Over Temperature",
    0x13: "FETs Over Temperature Quick",
    0x14: "Internal Fault #4",
    0x16: "Stacker Mode Fault",
    0x17: "Stacker Sync Clock Lost",
    0x18: "Stacker Sync Clock Out of Phase",
    0x19: "Stacker AC Phase Fault",
    0x20: "Over Temperature Shutdown",
    0x21: "Transfer Relay Fault",
    0x80: "Charger Fault",
    0x81: "Battery Temperature High",
    0x90: "Transformer Temperature Cutout Open",
    0x91: "AC Breaker CB3 Tripped",
}

# model_id -> human readable model name
MODEL_NAMES = {
    6: "MM612",
    7: "MM612-AE",
    8: "MM1212",
    9: "MMS1012",
    10: "MM1012E",
    11: "MM1512",
    15: "ME1512",
    20: "ME2012",
    25: "ME2512",
    30: "ME3112",
    35: "MS2012",
    40: "MS2012E",
    45: "MS2812",
    47: "MS2712E",
    53: "MM1324E",
    54: "MM1524",
    55: "RD1824",
    59: "RD2624E",
    63: "RD2824",
    69: "RD4024E",
    74: "RD3924",
    90: "MS4124E",
    91: "MS2024",
    105: "MS4024",
    106: "MS4024AE",
    107: "MS4024PAE",
    111: "MS4448AE",
    112: "MS3748AEJ",
    115: "MS4448PAE",
    116: "MS3748PAEJ",
}

STACK_MODE = {
    0x0: "Standalone Unit",
    0x1: "Master in Parallel Stack",
    0x2: "Slave in Parallel Stack",
    0x4: "Master in Series Stack",
    0x8: "Slave in Series Stack",
}

BATTERY_TYPE = {
    2: "Gel",
    4: "Flooded",
    8: "AGM",
    10: "AGM2",
    # anything > 100 is "Custom" -- handled in code, not the table
}

FORCE_CHARGE_MODE = {
    0x10: "Disable Refloat",
    0x20: "Force Silent",
    0x40: "Force Float",
    0x80: "Force Bulk",
}

GENSTART_AUTO_MODE = {
    0: "Off",
    1: "Enable",
    2: "Test",
    4: "Enable with Quiet Time",
    5: "On",
}

# Quirky raw->real AC trip-volts remap that exists in the original code.
# Documented here as data instead of buried in a chain of ifs.
AC_TRIP_VOLTS_REMAP = {
    110: 60,
    122: 65,
    135: 70,
    145: 75,
    155: 80,
    165: 85,
    175: 90,
    182: 95,
    190: 90,
}

AGS_QUIET_HOURS = {
    0: "Off",
    1: "21h - 07h",
    2: "21h - 09h",
    3: "21h - 09h",
    4: "22h - 08h",
    5: "23h - 08h",
}

AGS_STATUS = {
    0: "Non Valid",
    1: "Off",
    2: "Ready",
    3: "Manual Run",
    4: "Inverter in Charge Mode",
    5: "In Quiet Time",
    6: "Start in Test Mode",
    7: "Start on Temperature",
    8: "Start on Voltage",
    9: "Fault Start on Test",
    10: "Fault Start on Temperature",
    11: "Fault Start on Voltage",
    12: "Start Time of Day",
    13: "Start State of Charge",
    14: "Start Exercise",
    15: "Fault Start Time of Day",
    16: "Fault Start State of Charge",
    17: "Fault Start Exercise",
    18: "Start on Amps",
    19: "Start on Topoff",
    20: "Non Valid",
    21: "Fault Start on Amps",
    22: "Fault Start on Topoff",
    23: "Non Valid",
    24: "Fault Maximum Run",
    25: "Gen Run Fault",
    26: "Generator in Warm Up",
    27: "Generator in Cool Down",
}

BMK_FAULT = {
    0: "Reserved",
    1: "No Faults",  # Magnum's docs say "Normal"
    2: "Fault Start",
}


def bus_voltage_for_model(model_id: int) -> int:
    """Return the nominal DC bus voltage (12/24/48) for a given model_id.

    The original code set this with three sequential (non-elif) ``if``
    statements that relied on later conditions overwriting earlier ones.
    That happens to work for the values Magnum actually uses, but it's
    an easy-to-misread footgun. Written as a plain threshold ladder here.
    """
    if model_id > 107:
        return 48
    if model_id > 47:
        return 24
    return 12
