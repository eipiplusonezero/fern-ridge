from magnum_monitor.decoder import decode_frame
from tests.test_models import make_inverter_buf


def _base_frame(footer: int, extra_len_to: int) -> bytearray:
    """Build a frame: 22-byte inverter block + remote_base (22..35) + detail
    bytes (36..) + footer marker, padded out to ``extra_len_to`` total bytes.
    """
    buf = make_inverter_buf()
    buf.extend(bytes(14))  # remote_base block, offsets 22-35
    buf[25] = 80  # battery_type (unknown code, but exercises the branch)
    buf[29] = 0x25  # parallel_threshold=50, force_charge="Force Silent"
    buf[30] = 1  # genstart_auto -> Enable
    buf[31] = 100  # battery_low_trip
    buf[32] = 110  # volts_ac_trip -> remapped to 60
    buf[33] = 120  # float_volts
    buf[34] = 5  # equalise delta
    buf[35] = 25  # absorb_time

    while len(buf) < extra_len_to:
        buf.append(0)
    if len(buf) > 42:
        buf[42] = footer
    return buf


def test_remote_a3_frame_no_pair():
    buf = _base_frame(footer=0xA3, extra_len_to=43)
    buf[36] = 40  # quiet_time_start raw -> 10.0
    buf[37] = 80  # quiet_time_stop raw -> 20.0
    buf[38] = 3  # exercise_days
    buf[39] = 12  # exercise_start_time raw -> 3.0
    buf[40] = 20  # exercise_run_time raw -> 2.0
    buf[41] = 5  # top_off

    decoded = decode_frame(bytes(buf))
    assert decoded is not None
    assert decoded.inverter.model_descr == "MS4448PAE"
    assert decoded.remote_base.volts_ac_trip == 60
    assert "remote_a3" in decoded.details
    a3 = decoded.details["remote_a3"]
    assert a3.ags_quiet_time_start == 10.0
    assert a3.ags_exercise_days == 3
    # no paired block for A3
    assert "ags1" not in decoded.details


def test_remote_a0_frame_decodes_paired_ags1():
    buf = _base_frame(footer=0xA0, extra_len_to=49)
    buf[36] = 5  # remote_hours
    buf[37] = 30  # remote_min
    buf[38] = 15  # ags_run_time raw -> 1.5
    buf[39] = 70  # ags_start_temp
    buf[40] = 100  # ags_start_volts_dc raw
    buf[41] = 2  # ags_quiet_hours code -> "21h - 09h"
    # AGS1 block, offsets 43-48
    buf[44] = 3  # ags_status -> Manual Run
    buf[45] = 15  # ags_revision raw -> 1.5
    buf[46] = 25  # ags_temperature
    buf[47] = 40  # ags_run_time raw -> 4.0
    buf[48] = 120  # ags_volts_dc raw

    decoded = decode_frame(bytes(buf))
    assert "remote_a0" in decoded.details
    assert "ags1" in decoded.details
    assert decoded.details["remote_a0"].ags_quiet_hours_descr == "21h - 09h"
    assert decoded.details["ags1"].ags_status_descr == "Manual Run"


def test_short_frame_returns_none():
    assert decode_frame(bytes(10)) is None


def test_inverter_only_frame():
    buf = make_inverter_buf()
    while len(buf) < 23:
        buf.append(0)
    decoded = decode_frame(bytes(buf))
    assert decoded is not None
    assert decoded.remote_base is None
    assert decoded.details is None
