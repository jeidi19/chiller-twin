"""OPC UA server: runs the simulation in (scaled) real time and exposes it to clients.

    python -m simulator serve --config configs/faults_example.yaml --speed 60 --loop

The information model comes from ``opcua_model.build_address_space`` and is passed in as
``build_fn``, so the server can be tested with a stub model.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import UTC, datetime

from asyncua import Server, ua

from simulator.config import SimulationConfig
from simulator.control import HysteresisController
from simulator.opcua_model import NAMESPACE_URI, AddressSpace, build_address_space
from simulator.simulation import iter_run

log = logging.getLogger(__name__)

DEFAULT_ENDPOINT = "opc.tcp://0.0.0.0:4840/chiller-twin/"
SETPOINT_RANGE_C = (-40.0, 10.0)

BuildFn = Callable[[Server, int, SimulationConfig], Awaitable[AddressSpace]]

_CASTS = {
    ua.VariantType.Double: float,
    ua.VariantType.Float: float,
    ua.VariantType.Boolean: bool,
    ua.VariantType.String: str,
}


async def variant_types(space: AddressSpace) -> dict[str, ua.VariantType]:
    """Read once the data type chosen in the information model for each telemetry node."""
    return {
        name: await node.read_data_type_as_variant_type() for name, node in space.telemetry.items()
    }


async def publish_record(
    space: AddressSpace,
    vtypes: dict[str, ua.VariantType],
    record: dict,
    ts: datetime,
) -> None:
    """Write one simulation record to the telemetry nodes with source timestamp ``ts``."""
    for name, node in space.telemetry.items():
        vtype = vtypes[name]
        value = _CASTS.get(vtype, lambda v: v)(record[name])
        await node.write_value(
            ua.DataValue(Value=ua.Variant(value, vtype), SourceTimestamp=ts, ServerTimestamp=ts)
        )


async def apply_setpoint(space: AddressSpace, controller: HysteresisController) -> None:
    """Apply the setpoint written by a client, ignoring values out of range."""
    value = float(await space.setpoint.read_value())
    if value == controller.params.setpoint_c:
        return
    low, high = SETPOINT_RANGE_C
    if not low <= value <= high:
        log.warning("Rejected setpoint %.1f °C (allowed %s..%s)", value, low, high)
        await space.setpoint.write_value(
            ua.Variant(controller.params.setpoint_c, ua.VariantType.Double)
        )
        return
    log.info("Setpoint changed: %.1f -> %.1f °C", controller.params.setpoint_c, value)
    controller.params = replace(controller.params, setpoint_c=value)


async def serve(
    config: SimulationConfig,
    endpoint: str = DEFAULT_ENDPOINT,
    speed: float = 60.0,
    loop: bool = False,
    build_fn: BuildFn = build_address_space,
) -> None:
    """Serve the simulation; ``speed`` = simulated seconds per real second (0 = no wait)."""
    server = Server()
    await server.init()
    server.set_endpoint(endpoint)
    server.set_server_name("Chiller Twin")
    idx = await server.register_namespace(NAMESPACE_URI)
    space = await build_fn(server, idx, config)
    vtypes = await variant_types(space)
    delay_s = config.sample_period_s / speed if speed > 0 else 0.0

    async with server:
        log.info("OPC UA server listening on %s (speed x%s)", endpoint, speed)
        setpoint_c = config.controller.setpoint_c
        while True:
            controller = HysteresisController(replace(config.controller, setpoint_c=setpoint_c))
            for record in iter_run(config, controller=controller):
                await apply_setpoint(space, controller)
                await publish_record(space, vtypes, record, datetime.now(UTC))
                await asyncio.sleep(delay_s)
            if not loop:
                break
            setpoint_c = controller.params.setpoint_c
            log.info("Batch finished, starting a new one")
