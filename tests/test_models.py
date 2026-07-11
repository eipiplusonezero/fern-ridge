from magnum_monitor import models
from magnum_monitor.constants import bus_voltage_for_model


def test_bus_voltage_thresholds():
    assert bus_voltage_for_model(6) == 12
    assert bus_voltage_for_model(53) == 24
    assert bus_voltage_for_model(115) == 48


def make_inverter_buf() -> bytearray:
    buf = bytearray(22)
    buf[0] = 0x40  # Inverting
    buf[1] = 0x00  # No Faults
    buf[2], buf[3] = divmod(550, 256)  # volts_dc raw 550 -> 55.0
    buf[4], buf[5] = divmod(100, 256)  # amps_dc raw 100 -> 100.0
    buf[6] = 120  # volts_ac_out
    buf[7] = 121  # volts_ac_in
    buf[10] = 26  # revision raw -> 2.6
    buf[11] = 45  # temp_battery
    buf[12] = 30  # temp_transformer
    buf[13] = 35  # temp_fet
    buf[14] = 115  # model_id -> MS4448PAE, 48V bus
    buf[15] = 0x04  # stack_mode -> Master in Series Stack
    buf[16] = 10  # amps_ac_in
    buf[17] = 8  # amps_ac_out
    buf[18], buf[19] = divmod(600, 256)  # frequency raw 600 -> 60.0
    buf[21] = 0xFF
    return buf


def test_inverter_status_decode():
    inv = models.InverterStatus.decode(bytes(make_inverter_buf()))
    assert inv.status_descr == "Inverting"
    assert inv.fault_descr == "No Faults"
    assert inv.volts_dc == 55.0
    assert inv.amps_dc == 100.0
    assert inv.volts_ac_out == 120
    assert inv.revision == 2.6
    assert inv.model_descr == "MS4448PAE"
    assert inv.system_bus_volts == 48
    assert inv.stack_mode_descr == "Master in Series Stack"
    assert inv.frequency_ac_out == 60.0


def test_unknown_codes_dont_crash():
    buf = make_inverter_buf()
    buf[0] = 0xEE  # not in the status table
    buf[14] = 250  # not in the model table
    inv = models.InverterStatus.decode(bytes(buf))
    assert inv.status_descr == "Unknown"
    assert inv.model_descr == "UNKNOWN"
