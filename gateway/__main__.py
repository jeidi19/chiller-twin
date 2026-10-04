"""OPC UA → MQTT gateway.

    python -m gateway        (configured with environment variables, see ``Settings``)

Subscribes to the chiller telemetry on the OPC UA server and publishes one MQTT message
per sample. The server writes the values of one sample with the same source timestamp:
``SnapshotAssembler`` groups the notifications by that timestamp, so every message is a
consistent snapshot. Reconnects to both sides on failure.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime

import paho.mqtt.client as mqtt
from asyncua import Client, Node, ua

from gateway import payload
from simulator.opcua_model import NAMESPACE_URI
from simulator.simulation import TELEMETRY_FIELDS

log = logging.getLogger("gateway")


@dataclass(frozen=True)
class Settings:
    opcua_endpoint: str = "opc.tcp://localhost:4840/chiller-twin/"
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    machine_id: str = "bc-01"
    publishing_interval_ms: float = 100.0

    @classmethod
    def from_env(cls) -> Settings:
        d = cls()
        return cls(
            opcua_endpoint=os.getenv("OPCUA_ENDPOINT", d.opcua_endpoint),
            mqtt_host=os.getenv("MQTT_HOST", d.mqtt_host),
            mqtt_port=int(os.getenv("MQTT_PORT", d.mqtt_port)),
            machine_id=os.getenv("MACHINE_ID", d.machine_id),
        )


@dataclass
class SnapshotAssembler:
    """Collects data-change notifications and emits complete snapshots in time order."""

    fields: tuple[str, ...] = TELEMETRY_FIELDS
    _pending: dict[datetime, dict] = field(default_factory=dict)
    _last_emitted: datetime | None = None

    def add(self, name: str, value, ts: datetime) -> tuple[datetime, dict] | None:
        """Add one value; return ``(ts, values)`` when the snapshot at ``ts`` is complete."""
        if self._last_emitted is not None and ts <= self._last_emitted:
            return None  # late duplicate of a snapshot already sent
        values = self._pending.setdefault(ts, {})
        values[name] = value
        if len(values) < len(self.fields):
            return None
        # Complete: drop it and any older, incomplete snapshot (a value was lost).
        for old in [t for t in self._pending if t <= ts]:
            del self._pending[old]
        self._last_emitted = ts
        return ts, values


class _Handler:
    """asyncua subscription handler: feeds the assembler, queues complete snapshots."""

    def __init__(self, names: dict[ua.NodeId, str], queue: asyncio.Queue) -> None:
        self.names = names
        self.queue = queue
        self.assembler = SnapshotAssembler()

    def datachange_notification(self, node: Node, val, data) -> None:
        ts = data.monitored_item.Value.SourceTimestamp
        if ts.tzinfo is None:  # asyncua returns naive datetimes, always in UTC
            ts = ts.replace(tzinfo=UTC)
        snapshot = self.assembler.add(self.names[node.nodeid], val, ts)
        if snapshot is not None:
            self.queue.put_nowait(snapshot)


async def find_telemetry_nodes(client: Client) -> dict[str, Node]:
    """Browse below the ``Chiller`` object and match variables by BrowseName."""
    idx = await client.get_namespace_index(NAMESPACE_URI)
    chiller = await client.nodes.objects.get_child(f"{idx}:Chiller")
    found: dict[str, Node] = {}
    stack = [chiller]
    while stack:
        for child in await stack.pop().get_children():
            name = await child.read_browse_name()
            if (
                name.NamespaceIndex == idx
                and name.Name in TELEMETRY_FIELDS
                and await child.read_node_class() == ua.NodeClass.Variable
            ):
                found[name.Name] = child
            stack.append(child)
    missing = set(TELEMETRY_FIELDS) - set(found)
    if missing:
        raise RuntimeError(f"Telemetry variables not found below Chiller: {sorted(missing)}")
    return found


def _monitored_item_requests(nodes: list[Node]) -> list[ua.MonitoredItemCreateRequest]:
    """Notify on every new source timestamp, not only when the value changes: a sample
    where e.g. ``compressor_on`` is unchanged must still complete its snapshot."""
    requests = []
    for handle, node in enumerate(nodes, start=1000):
        params = ua.MonitoringParameters()
        params.ClientHandle = handle
        params.SamplingInterval = 0.0
        params.QueueSize = 100
        params.DiscardOldest = True
        params.Filter = ua.DataChangeFilter(Trigger=ua.DataChangeTrigger.StatusValueTimestamp)
        request = ua.MonitoredItemCreateRequest()
        request.ItemToMonitor = ua.ReadValueId(
            NodeId=node.nodeid, AttributeId=ua.AttributeIds.Value
        )
        request.MonitoringMode = ua.MonitoringMode.Reporting
        request.RequestedParameters = params
        requests.append(request)
    return requests


def connect_mqtt(settings: Settings) -> mqtt.Client:
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2, client_id=f"gateway-{settings.machine_id}"
    )
    client.on_connect = lambda c, u, f, rc, p: log.info("MQTT connected (%s)", rc)
    client.on_disconnect = lambda c, u, f, rc, p: log.warning("MQTT disconnected (%s)", rc)
    client.connect_async(settings.mqtt_host, settings.mqtt_port)
    client.loop_start()  # background thread, reconnects automatically
    return client


async def bridge(settings: Settings, mqtt_client: mqtt.Client) -> None:
    """One OPC UA session: subscribe and forward until the connection drops."""
    if payload.QOS is None or payload.RETAIN is None:
        raise NotImplementedError("Choose QOS and RETAIN in gateway/payload.py")
    async with Client(settings.opcua_endpoint) as client:
        nodes = await find_telemetry_nodes(client)
        queue: asyncio.Queue = asyncio.Queue()
        handler = _Handler({n.nodeid: name for name, n in nodes.items()}, queue)
        subscription = await client.create_subscription(settings.publishing_interval_ms, handler)
        await subscription.create_monitored_items(_monitored_item_requests(list(nodes.values())))
        log.info("Subscribed to %d variables on %s", len(nodes), settings.opcua_endpoint)
        while True:
            try:
                ts, values = await asyncio.wait_for(queue.get(), timeout=5.0)
            except TimeoutError:
                await client.check_connection()  # raises if the session is gone
                continue
            topic, body = payload.to_payload(settings.machine_id, values, ts)
            mqtt_client.publish(topic, body, qos=payload.QOS, retain=payload.RETAIN)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    logging.getLogger("asyncua").setLevel(logging.WARNING)
    settings = Settings.from_env()
    mqtt_client = connect_mqtt(settings)
    delay_s = 1.0
    while True:
        try:
            await bridge(settings, mqtt_client)
        except NotImplementedError:
            raise
        except Exception as exc:  # network errors of any kind: retry with backoff
            log.warning("OPC UA connection lost (%s), retrying in %.0f s", exc, delay_s)
            await asyncio.sleep(delay_s)
            delay_s = min(delay_s * 2, 30.0)
        else:
            delay_s = 1.0


if __name__ == "__main__":
    asyncio.run(main())
