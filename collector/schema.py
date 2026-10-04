"""InfluxDB schema: how one MQTT message becomes a point in the time series database.

>>> TODO (Jacopo): implement ``to_point()``. The tests in ``tests/test_schema.py`` are
>>> ``xfail`` and start passing when it is done (then remove their ``pytestmark``).

Contract:

- input: the topic and payload produced by ``gateway.payload.to_payload``;
- a topic that is not ``chiller/<machine_id>/telemetry`` raises ``ValueError``;
- output: one ``influxdb_client.Point`` with
  - a measurement name of your choice,
  - the tag ``machine_id`` taken from the topic,
  - the time taken from the payload ``"ts"`` (not the arrival time),
  - temperatures (including ``active_setpoint_c``) and power as float fields,
    ``compressor_on`` and ``door_open`` as fields (bool or 0/1, your choice),
  - ``label`` as a tag *or* a field: your choice, be ready to defend it.

Useful: ``Point("name").tag(k, v).field(k, v).time(dt)``.

Questions worth thinking about (interviewers ask them):
- Tag or field: which are indexed, which can you ``group by``/filter on efficiently?
- What is *series cardinality* and why do tags with many distinct values hurt InfluxDB?
  Would ``label`` hurt? Would a ``batch_id`` tag?
- One measurement with many fields vs one measurement per variable: impact on queries
  (Flux ``pivot``) and on storage.
- Which precision (s, ms, ns) does the timestamp need here?
"""

from __future__ import annotations

from influxdb_client import Point


def to_point(topic: str, payload: bytes) -> Point:
    """Convert one telemetry message into an InfluxDB point."""
    raise NotImplementedError("InfluxDB schema not implemented yet: see the docstring.")
