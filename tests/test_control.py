from simulator.config import ControllerParams
from simulator.control import HysteresisController

PARAMS = ControllerParams(setpoint_c=-18.0, hysteresis_c=2.0, min_on_time_s=60, min_off_time_s=120)


def test_turns_on_above_band_and_off_below_band():
    c = HysteresisController(PARAMS)
    assert c.update(-10.0, 1.0) is True
    for _ in range(60):
        c.update(-18.0, 1.0)  # inside the band: keeps running
    assert c.compressor_on is True
    assert c.update(-19.5, 1.0) is False


def test_respects_min_on_time():
    c = HysteresisController(PARAMS)
    c.update(-10.0, 1.0)
    assert c.update(-25.0, 1.0) is True  # too cold, but ran only 1 s


def test_respects_min_off_time():
    c = HysteresisController(PARAMS)
    c.update(-10.0, 1.0)
    for _ in range(60):
        c.update(-25.0, 1.0)
    assert c.compressor_on is False
    assert c.update(-10.0, 1.0) is False  # too warm, but stopped only 1 s ago
    for _ in range(120):
        c.update(-10.0, 1.0)
    assert c.compressor_on is True
