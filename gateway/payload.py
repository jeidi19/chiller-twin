"""MQTT message format: how one sample of the machine travels on the broker.

One message per sample, an atomic snapshot of all the values with one timestamp:

    topic:    chiller/<machine_id>/telemetry
    payload:  {"ts": "2026-10-03T12:00:05+00:00", "cell_temp_c": -17.8, ...}   (UTF-8 JSON)

- ``ts`` is the *source* timestamp (when the sample was taken), ISO 8601 with timezone,
  so network delays and reconnections do not shift or reorder the data;
- the values of ``TELEMETRY_FIELDS`` sit at the top level next to ``ts`` (flat JSON,
  simple to read back in ``collector/schema.py``);
- a ``machine_id`` that is empty or contains ``/``, ``+`` or ``#`` is rejected: it would
  add a topic level or act as an MQTT wildcard.

Delivery choices:

- ``QOS = 1`` (at least once): with QoS 0 paho drops the messages published while the
  broker is unreachable, so an outage would leave a gap in the data and distort the ML
  features. With QoS 1 they are queued and re-sent after reconnecting; a duplicate is
  harmless because InfluxDB overwrites a point with the same series and timestamp.
  Limit: the queue lives in memory, so it is lost if the gateway itself restarts.
- ``RETAIN = False``: this is a continuous stream; a retained sample would be delivered
  to late subscribers as if it were new, even with the machine off. Retain belongs on a
  separate status topic (online/offline with a Last Will), a possible extension.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

QOS: int = 1
RETAIN: bool = False


def to_payload(machine_id: str, values: dict, ts: datetime) -> tuple[str, bytes]:
    """Return ``(topic, payload)`` for one sample of ``machine_id`` taken at ``ts``."""
    if machine_id == "" or any(c in machine_id for c in "/+#"):
        raise ValueError(f"invalid machine_id {machine_id!r}")
    topic = f"chiller/{machine_id}/telemetry"
    if ts.tzinfo is None:
        raise ValueError(f"naive datetime {ts!r} (no tzinfo)")

    data = {"ts": ts.astimezone(UTC).isoformat(), **values}
    payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
    return topic, payload
