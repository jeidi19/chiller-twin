"""InfluxDB schema: how one MQTT message becomes a point in the time series database.

One point per message, in the measurement ``chiller``:

    chiller,label=normal,machine_id=bc-01 cell_temp_c=-17.8,...,door_open=false <ts in ns>

- tags (indexed, for filtering and grouping): ``machine_id``, taken from the topic, and
  ``label``. ``label`` has few distinct values (normal + 4 faults), so its cardinality
  stays low; the price is that a machine moves to another series when a fault starts;
- float fields: temperatures, active setpoint and power, always converted with
  ``float()`` because InfluxDB fixes a field type at the first write and would reject a
  later integer;
- bool fields: ``compressor_on`` and ``door_open``;
- time: the source timestamp ``ts`` of the payload, not the arrival time, at the default
  nanosecond precision (samples arrive every ~0.17 s at ``--speed 60``: second precision
  would make them overwrite each other).

The schema is declared explicitly (which keys are tags, float or bool fields) instead of
being inferred from the value types, and unknown keys are ignored, so the schema cannot
grow by accident.

Malformed messages must raise ``ValueError``: the collector skips them, while any other
exception would stop its MQTT loop (paho does not suppress callback exceptions).
"""

from __future__ import annotations

import json
from datetime import datetime

from influxdb_client import Point

TAGS = {"label"}
FLOAT_FIELDS = {
    "cell_temp_c",
    "product_temp_c",
    "active_setpoint_c",
    "compressor_power_w",
}
BOOL_FIELDS = {"compressor_on", "door_open"}
MEASUREMENT = "chiller"


def to_point(topic: str, payload: bytes) -> Point:
    """Convert one telemetry message into an InfluxDB point."""
    parts = topic.split("/")
    if len(parts) != 3:
        raise ValueError(f"invalid topic {topic!r}")
    prefix, machine_id, suffix = parts
    if prefix != "chiller" or suffix != "telemetry" or not machine_id:
        raise ValueError(f"invalid topic {topic!r}")
    data = json.loads(payload.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"invalid payload {payload!r}")
    try:
        timestamp = datetime.fromisoformat(data["ts"])
        if timestamp.tzinfo is None:
            raise ValueError(f"naive datetime {timestamp!r} (no tzinfo)")
    except (ValueError, KeyError, TypeError) as err:
        raise ValueError(f"invalid timestamp in message {data!r}") from err
    point = Point(MEASUREMENT).tag("machine_id", machine_id).time(timestamp)
    for key in TAGS:
        try:
            point.tag(key, str(data[key]))
        except KeyError as err:
            raise ValueError(f"missing tag {key!r} in message {data!r}") from err
    for key in FLOAT_FIELDS:
        try:
            point.field(key, float(data[key]))
        except KeyError as err:
            raise ValueError(f"missing float field {key!r} in message {data!r}") from err
        except (TypeError, ValueError) as err:
            raise ValueError(f"invalid float field {key!r} in message {data!r}") from err
    for key in BOOL_FIELDS:
        try:
            if isinstance(data[key], bool):
                point.field(key, data[key])
            else:
                raise ValueError(f"not a bool: {data[key]!r}")
        except KeyError as err:
            raise ValueError(f"missing bool field {key!r} in message {data!r}") from err
        except (TypeError, ValueError) as err:
            raise ValueError(f"invalid bool field {key!r} in message {data!r}") from err

    return point
