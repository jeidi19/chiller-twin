"""Behavioural spec of the InfluxDB schema (collector/schema.py), including a round trip
with the MQTT format of gateway/payload.py.

The tests at the bottom check that malformed messages raise ValueError, the only
exception the collector skips.
"""

import json

import pytest

from collector.schema import to_point
from gateway.payload import to_payload
from tests.test_payload import TS, VALUES


def point_parts(point):
    """(measurement, tags, fields, time) of an influxdb_client Point."""
    return point._name, dict(point._tags), dict(point._fields), point._time


def test_round_trip_keeps_every_value():
    measurement, tags, fields, time = point_parts(to_point(*to_payload("bc-01", VALUES, TS)))
    assert measurement
    assert tags["machine_id"] == "bc-01"
    assert time == TS
    for name in ("cell_temp_c", "product_temp_c", "active_setpoint_c", "compressor_power_w"):
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


def test_int_value_is_written_as_float():
    """InfluxDB fixes a field type at the first write: 0 must not become an integer."""
    topic, body = to_payload("bc-01", {**VALUES, "compressor_power_w": 0}, TS)
    _, _, fields, _ = point_parts(to_point(topic, body))
    assert isinstance(fields["compressor_power_w"], float)


# --- Malformed messages ---------------------------------------------------------------
# The collector skips a message only on ValueError: any other exception stops it.

TOPIC = "chiller/bc-01/telemetry"
MESSAGE = json.loads(to_payload("bc-01", VALUES, TS)[1])


def without(key):
    return json.dumps({k: v for k, v in MESSAGE.items() if k != key}).encode()


def with_value(key, value):
    return json.dumps({**MESSAGE, key: value}).encode()


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(b"\xff\xfe", id="invalid-utf8"),
        pytest.param(b"not json", id="not-json"),
        pytest.param(b"[1, 2]", id="array"),
        pytest.param(b"42", id="number"),
        pytest.param(b"null", id="null"),
    ],
)
def test_undecodable_or_non_object_payload_is_rejected(body):
    with pytest.raises(ValueError):
        to_point(TOPIC, body)


def test_missing_timestamp_is_rejected():
    with pytest.raises(ValueError):
        to_point(TOPIC, without("ts"))


def test_naive_timestamp_is_rejected():
    with pytest.raises(ValueError):
        to_point(TOPIC, with_value("ts", "2026-10-03T12:00:05"))


@pytest.mark.parametrize("key", ["cell_temp_c", "compressor_on", "label"])
def test_missing_value_is_rejected(key):
    """A partial point would hide a gap in the data: the gateway always sends all values."""
    with pytest.raises(ValueError):
        to_point(TOPIC, without(key))


@pytest.mark.parametrize("value", ["false", "true", None, 2])
def test_non_boolean_state_is_rejected(value):
    """bool("false") is True: only true/false (or 0/1) are valid states."""
    with pytest.raises(ValueError):
        to_point(TOPIC, with_value("door_open", value))
