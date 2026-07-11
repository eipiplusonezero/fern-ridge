"""Decoders for each packet type in the Magnum MagNet protocol.

Each packet type is an immutable ``dataclass`` built via a ``decode``
classmethod that takes the raw frame (a ``bytes`` object) plus whatever
shared context it needs (currently just ``system_bus_volts``, which the
inverter packet determines and the remote/AGS packets depend on).

Design notes vs. the original script:

* No ``ord()``. In Python 3, indexing a ``bytes`` object already gives you
  an ``int`` -- ``buf[i]`` replaces ``ord(packet_buffer[i])``. This is the
  actual reason the original raises ``TypeError`` under Python 3.
* No module-level ``global system_bus_volts``. It's threaded through as an
  explicit argument, so each decoder is a pure function of its inputs and
  can be unit tested in isolation.
* No mutable class-level defaults doubling as instance state. Dataclasses
  give each instance its own fields.
* Byte offsets are named constants next to their use, matching the layout
  documented in the original file's header comment.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

from . import constants as c


def _u16(buf: bytes, hi: int) -> int:
    """Big-endian 16-bit value starting at offset ``hi``."""
    return (buf[hi] << 8) | buf[hi + 1]


def _signed16_tenths(raw: int) -> float:
    """Some 16-bit fields are signed via two's-complement-ish wraparound
    (`if > 32768: value = 65535 - value`) rather than proper signed decode.
    Reproduced faithfully since we don't have Magnum's actual signed
    format confirmed -- flagged here so it's easy to find and fix later.
    """
    if raw > 32768:
        raw = 65535 - raw
    return raw


@dataclass(frozen=True)
class InverterStatus:
    status_code: int
    status_descr: str
    fault_code: int
    fault_descr: str
    volts_dc: float
    amps_dc: float
    volts_ac_out: int
    volts_ac_in: int
    revision: float
    temp_battery: int
    temp_transformer: int
    temp_fet: int
    model_id: int
    model_descr: str
    stack_mode_code: int
    stack_mode_descr: str
    amps_ac_in: int
    amps_ac_out: int
    frequency_ac_out: float
    system_bus_volts: int

    @classmethod
    def decode(cls, buf: bytes) -> "InverterStatus":
        status_code = buf[0]
        fault_code = buf[1]
        model_id = buf[14]
        system_bus_volts = c.bus_voltage_for_model(model_id)
        return cls(
            status_code=status_code,
            status_descr=c.INVERTER_STATUS.get(status_code, "Unknown"),
            fault_code=fault_code,
            fault_descr=c.INVERTER_FAULT.get(fault_code, "Unknown"),
            volts_dc=_u16(buf, 2) / 10.0,
            amps_dc=float(_u16(buf, 4)),
            volts_ac_out=buf[6],
            volts_ac_in=buf[7],
            revision=buf[10] / 10.0,
            temp_battery=buf[11],
            temp_transformer=buf[12],
            temp_fet=buf[13],
            model_id=model_id,
            model_descr=c.MODEL_NAMES.get(model_id, "UNKNOWN"),
            stack_mode_code=buf[15],
            stack_mode_descr=c.STACK_MODE.get(buf[15], "Unknown"),
            amps_ac_in=buf[16],
            amps_ac_out=buf[17],
            frequency_ac_out=_u16(buf, 18) / 10.0,
            system_bus_volts=system_bus_volts,
        )


@dataclass(frozen=True)
class RemoteBase:
    battery_size: int
    battery_type: int
    battery_type_descr: str
    charger_amps: int
    shore_ac_amps: int
    revision: float
    parallel_threshold: int
    force_charge_descr: str
    genstart_auto_descr: str
    battery_low_trip: float
    volts_ac_trip: int
    float_volts: float
    absorb_volts: float
    equalise_volts: float
    absorb_time: float

    @classmethod
    def decode(cls, buf: bytes, system_bus_volts: int) -> "RemoteBase":
        scale = {12: 1, 24: 2, 48: 4}[system_bus_volts]

        battery_type = buf[25]
        if battery_type > 100:
            battery_type_descr = "Custom"
        else:
            battery_type_descr = c.BATTERY_TYPE.get(battery_type, "Unknown")
        absorb_volts = (battery_type * scale) / 10.0

        force_charge_code = buf[29] & 0xF0
        genstart_auto = buf[30]

        raw_trip = buf[32]
        volts_ac_trip = c.AC_TRIP_VOLTS_REMAP.get(raw_trip, raw_trip)

        battery_low_scale = 2 if system_bus_volts == 48 else 1
        equalise_scale = scale

        return cls(
            battery_size=buf[24] * 10,
            battery_type=battery_type,
            battery_type_descr=battery_type_descr,
            charger_amps=buf[26],
            shore_ac_amps=buf[27],
            revision=buf[28] / 10.0,
            parallel_threshold=(buf[29] & 0x0F) * 10,
            force_charge_descr=c.FORCE_CHARGE_MODE.get(force_charge_code, "None"),
            genstart_auto_descr=c.GENSTART_AUTO_MODE.get(genstart_auto, "Unknown"),
            battery_low_trip=(buf[31] * battery_low_scale) / 10.0,
            volts_ac_trip=volts_ac_trip,
            float_volts=(buf[33] * scale) / 10.0,
            absorb_volts=absorb_volts,
            equalise_volts=absorb_volts + (buf[34] * scale) / 10.0,
            absorb_time=buf[35] / 10.0,
        )


@dataclass(frozen=True)
class RemoteA0:
    remote_hours: int
    remote_min: int
    ags_run_time: float
    ags_start_temp: int
    ags_start_volts_dc: float
    ags_quiet_hours_descr: str

    @classmethod
    def decode(cls, buf: bytes, system_bus_volts: int) -> "RemoteA0":
        scale = {12: 1, 24: 2, 48: 4}[system_bus_volts]
        quiet_hours_code = buf[41]
        return cls(
            remote_hours=buf[36],
            remote_min=buf[37],
            ags_run_time=buf[38] / 10.0,
            ags_start_temp=buf[39],
            ags_start_volts_dc=(buf[40] * scale) / 10.0,
            ags_quiet_hours_descr=c.AGS_QUIET_HOURS.get(quiet_hours_code, "Unknown"),
        )


@dataclass(frozen=True)
class AGS1:
    ags_status_code: int
    ags_status_descr: str
    ags_revision: float
    ags_temperature: int
    ags_run_time: float
    ags_volts_dc: float

    @classmethod
    def decode(cls, buf: bytes, system_bus_volts: int) -> "AGS1":
        scale = {12: 1, 24: 2, 48: 4}[system_bus_volts]
        status_code = buf[44]
        return cls(
            ags_status_code=status_code,
            ags_status_descr=c.AGS_STATUS.get(status_code, "Unknown"),
            ags_revision=buf[45] / 10.0,
            ags_temperature=buf[46],
            ags_run_time=buf[47] / 10.0,
            ags_volts_dc=(buf[48] * scale) / 10.0,
        )


@dataclass(frozen=True)
class RemoteA1:
    ags_start_time: float
    ags_stop_time: float
    ags_start_stop_enabled: bool
    ags_volts_dc_stop: float
    ags_start_delay_s: int
    ags_stop_delay_s: int
    ags_max_run_time: float

    @classmethod
    def decode(cls, buf: bytes, system_bus_volts: int) -> "RemoteA1":
        scale = {12: 1, 24: 2, 48: 4}[system_bus_volts]

        def delay_seconds(raw: int) -> int:
            # MSB set -> value is in minutes, not seconds
            return (raw & 0x7F) * 60 if raw & 0x80 else raw

        return cls(
            ags_start_time=buf[36] * 0.25,
            ags_stop_time=buf[37] * 0.25,
            ags_start_stop_enabled=buf[36] != buf[37],
            ags_volts_dc_stop=(buf[38] * scale) / 10.0,
            ags_start_delay_s=delay_seconds(buf[39]),
            ags_stop_delay_s=delay_seconds(buf[40]),
            ags_max_run_time=buf[41] / 10.0,
        )


@dataclass(frozen=True)
class AGS2:
    ags_days_last_gen_run: int

    @classmethod
    def decode(cls, buf: bytes, system_bus_volts: int) -> "AGS2":
        return cls(ags_days_last_gen_run=buf[44])


@dataclass(frozen=True)
class RemoteA2:
    ags_soc_start: int
    ags_soc_stop: int
    ags_amps_start: int
    ags_amps_start_delay_s: int
    ags_amps_stop: int
    ags_amps_stop_delay_s: int

    @classmethod
    def decode(cls, buf: bytes, system_bus_volts: int) -> "RemoteA2":
        def delay_seconds(raw: int) -> int:
            return (raw & 0x7F) * 60 if raw & 0x80 else raw

        return cls(
            ags_soc_start=buf[36],
            ags_soc_stop=buf[37],
            ags_amps_start=buf[38],
            ags_amps_start_delay_s=delay_seconds(buf[39]),
            ags_amps_stop=buf[40],
            ags_amps_stop_delay_s=delay_seconds(buf[41]),
        )


@dataclass(frozen=True)
class RTR:
    rtr_revision: float

    @classmethod
    def decode(cls, buf: bytes, system_bus_volts: int) -> "RTR":
        return cls(rtr_revision=buf[44] / 10.0)


@dataclass(frozen=True)
class RemoteA3:
    ags_quiet_time_start: float
    ags_quiet_time_stop: float
    ags_exercise_days: int
    ags_exercise_start_time: float
    ags_exercise_run_time: float
    ags_top_off: int

    @classmethod
    def decode(cls, buf: bytes, system_bus_volts: int) -> "RemoteA3":
        return cls(
            ags_quiet_time_start=buf[36] * 0.25,
            ags_quiet_time_stop=buf[37] * 0.25,
            ags_exercise_days=buf[38],
            ags_exercise_start_time=buf[39] * 0.25,
            ags_exercise_run_time=buf[40] / 10.0,
            ags_top_off=buf[41],
        )


@dataclass(frozen=True)
class RemoteA4:
    ags_warm_up_time_s: int
    ags_cool_down_time_s: int

    @classmethod
    def decode(cls, buf: bytes, system_bus_volts: int) -> "RemoteA4":
        def delay_seconds(raw: int) -> int:
            return (raw & 0x7F) * 60 if raw & 0x80 else raw

        return cls(
            ags_warm_up_time_s=delay_seconds(buf[36]),
            ags_cool_down_time_s=delay_seconds(buf[37]),
        )


@dataclass(frozen=True)
class RemoteZ0:
    remote_hours: int
    remote_min: int

    @classmethod
    def decode(cls, buf: bytes, system_bus_volts: int) -> "RemoteZ0":
        return cls(remote_hours=buf[36], remote_min=buf[37])


@dataclass(frozen=True)
class RemoteBMK:
    remote_hours: int
    remote_min: int
    bmk_battery_efficiency: int
    bmk_resets: int
    bmk_battery_size: int

    @classmethod
    def decode(cls, buf: bytes, system_bus_volts: int) -> "RemoteBMK":
        return cls(
            remote_hours=buf[36],
            remote_min=buf[37],
            bmk_battery_efficiency=buf[38],
            bmk_resets=buf[39],
            bmk_battery_size=buf[40] * 10,
        )


@dataclass(frozen=True)
class BMK:
    soc: int
    volts_dc: float
    amps_dc: float
    volts_min: float
    volts_max: float
    amp_hour_net: float
    amp_hour_trip: float
    amp_hour_total: float
    revision: float
    fault_code: int
    fault_descr: str

    @classmethod
    def decode(cls, buf: bytes, system_bus_volts: int) -> "BMK":
        amps_dc = _signed16_tenths(_u16(buf, 47)) / 10.0
        amp_hour_net = _signed16_tenths(_u16(buf, 53))
        fault_code = buf[60]
        return cls(
            soc=buf[44],
            volts_dc=_u16(buf, 45) / 100.0,
            amps_dc=amps_dc,
            volts_min=_u16(buf, 49) / 100.0,
            volts_max=_u16(buf, 51) / 100.0,
            amp_hour_net=amp_hour_net,
            amp_hour_trip=_u16(buf, 55) / 10.0,
            amp_hour_total=_u16(buf, 57) * 100.0,
            revision=buf[59] / 10.0,
            fault_code=fault_code,
            fault_descr=c.BMK_FAULT.get(fault_code, "Unknown"),
        )


def to_dict(obj) -> dict:
    """JSON-friendly dict for any of the dataclasses above."""
    return asdict(obj)
