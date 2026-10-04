"""Behavioural spec of the InfluxDB schema (collector/schema.py), including a round trip
with the MQTT format of gateway/payload.py.

xfail until both are implemented: then remove the ``pytestmark`` line.
"""

import pytest

from collector.schema import to_point
from gateway.payload import to_payload
from tests.test_payload import TS, VALUES

pytestmark = pytest.mark.xfail(raises=NotImplementedError, strict=True)


def point_parts(point):
    """(measurement, tags, fields, time) of an influxdb_client Point."""
    return point._name, dict(point._tags), dict(point._fields), point._time


def test_round_trip_keeps_every_value():
    measurement, tags, fields, time = point_parts(to_point(*to_payload("bc-01", VALUES, TS)))
    assert measurement
    assert tags["machine_id"] == "bc-01"
    assert time == TS
    for name in ("cell_temp_c", "product_temp_c", "compressor_power_w"):
        assert isinstance(fields[name], float)
        assert fields[name] == pytest.approx(VALUES[name])
    for name in ("compressor_on", "door_open"):
        assert bool(fields[name]) is VALUES[name]
    assert {**tags, **fields}["label"] == "normal"


def test_wrong_topic_is_rejected():
    _, body = to_payload("bc-01", VALUES, TS)
    for topic in ("chiller/bc-01/status", "plant/bc-01/telemetry", "chiller/telemetry"):
        with pytest.raises(ValueError):
            to_point(topic, body)
