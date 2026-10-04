"""Behavioural spec of the MQTT message format (gateway/payload.py).

xfail until to_payload() is implemented: then remove the ``pytestmark`` line.
"""

import json
from datetime import UTC, datetime

import pytest

from gateway import payload
from gateway.payload import to_payload

TS = datetime(2026, 10, 3, 12, 0, 5, tzinfo=UTC)
VALUES = {
    "cell_temp_c": -17.8,
    "product_temp_c": 12.3,
    "active_setpoint_c": -18.0,
    "compressor_on": True,
    "compressor_power_w": 2000.0,
    "door_open": False,
    "label": "normal",
}


def test_qos_and_retain_are_chosen():
    if payload.QOS is None or payload.RETAIN is None:
        raise NotImplementedError("choose QOS and RETAIN")
    assert payload.QOS in (0, 1, 2)
    assert isinstance(payload.RETAIN, bool)


def test_topic():
    topic, _ = to_payload("bc-01", VALUES, TS)
    assert topic == "chiller/bc-01/telemetry"


def test_payload_is_json_with_source_timestamp():
    _, body = to_payload("bc-01", VALUES, TS)
    message = json.loads(body.decode("utf-8"))
    assert isinstance(message, dict)
    assert datetime.fromisoformat(message["ts"]) == TS


@pytest.mark.parametrize("machine_id", ["", "a/b", "a+", "a#"])
def test_invalid_machine_id_is_rejected(machine_id):
    with pytest.raises(ValueError):
        to_payload(machine_id, VALUES, TS)


def test_naive_timestamp_is_rejected():
    with pytest.raises(ValueError):
        to_payload("bc-01", VALUES, TS.replace(tzinfo=None))
