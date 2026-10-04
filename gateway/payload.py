"""MQTT message format: how one sample of the machine travels on the broker.

>>> TODO (Jacopo): implement ``to_payload()`` and choose ``QOS`` and ``RETAIN``.
>>> The tests in ``tests/test_payload.py`` are ``xfail`` and start passing when it is
>>> done (then remove their ``pytestmark``). ``collector/schema.py`` must be able to
>>> read what you produce here: a round-trip test checks the two together.

Contract:

- one message per sample (an atomic snapshot of all the values, one timestamp);
- topic ``chiller/<machine_id>/telemetry``; a ``machine_id`` that is empty or contains
  ``/``, ``+`` or ``#`` raises ``ValueError`` (they would break the topic tree);
- payload: UTF-8 JSON object with a ``"ts"`` key, the *source* timestamp in ISO 8601
  with timezone; a naive ``datetime`` (no tzinfo) raises ``ValueError``;
- the layout of the values inside the JSON is your choice.

Questions worth thinking about (interviewers ask them):
- QoS 0, 1 or 2: what does each guarantee, what does it cost, which fits telemetry
  sampled every few seconds? And for an alarm?
- ``retain``: what does a client that subscribes *now* receive? Useful here?
- One JSON message per sample vs one topic per variable (``.../cell_temp_c``): pros and
  cons for bandwidth, consistency and consumers. What does Sparkplug B do?
- Why carry the source timestamp in the payload instead of using the arrival time?
"""

from __future__ import annotations

from datetime import datetime

QOS: int | None = None  # TODO (Jacopo): 0, 1 or 2
RETAIN: bool | None = None  # TODO (Jacopo)


def to_payload(machine_id: str, values: dict, ts: datetime) -> tuple[str, bytes]:
    """Return ``(topic, payload)`` for one sample of ``machine_id`` taken at ``ts``."""
    raise NotImplementedError("MQTT payload not implemented yet: see the docstring.")
