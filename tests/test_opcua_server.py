"""OPC UA server plumbing, tested in-process with a stub information model."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from asyncua import Server, ua

from simulator.config import load_config
from simulator.control import HysteresisController
from simulator.opcua_model import NAMESPACE_URI, AddressSpace
from simulator.opcua_server import apply_setpoint, publish_record, variant_types
from simulator.simulation import TELEMETRY_FIELDS

CONFIG = load_config(Path(__file__).parent.parent / "configs" / "default.yaml")

TYPES = {
    "cell_temp_c": ua.VariantType.Double,
    "product_temp_c": ua.VariantType.Double,
    "compressor_on": ua.VariantType.Boolean,
    "compressor_power_w": ua.VariantType.Double,
    "door_open": ua.VariantType.Boolean,
    "label": ua.VariantType.String,
}
EMPTY = {
    ua.VariantType.Double: 0.0,
    ua.VariantType.Boolean: False,
    ua.VariantType.String: "",
}


async def stub_space():
    """Flat stub model: one variable per field, directly under Chiller."""
    server = Server()
    await server.init()
    idx = await server.register_namespace(NAMESPACE_URI)
    chiller = await server.nodes.objects.add_object(idx, "Chiller")
    telemetry = {
        name: await chiller.add_variable(idx, name, EMPTY[TYPES[name]], varianttype=TYPES[name])
        for name in TELEMETRY_FIELDS
    }
    setpoint = await chiller.add_variable(
        idx, "setpoint_c", CONFIG.controller.setpoint_c, varianttype=ua.VariantType.Double
    )
    await setpoint.set_writable()
    return AddressSpace(telemetry, setpoint)


def test_publish_record_casts_to_the_model_types():
    record = {
        "t_s": 10.0,
        "cell_temp_c": -17.5,
        "product_temp_c": 40.0,
        "compressor_on": 1,
        "compressor_power_w": 2000.0,
        "door_open": 0,
        "label": "normal",
    }
    ts = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)

    async def scenario():
        space = await stub_space()
        await publish_record(space, await variant_types(space), record, ts)
        values = {n: await node.read_value() for n, node in space.telemetry.items()}
        source_ts = (await space.telemetry["cell_temp_c"].read_data_value()).SourceTimestamp
        return values, source_ts

    values, source_ts = asyncio.run(scenario())
    assert values["cell_temp_c"] == -17.5
    assert values["compressor_on"] is True
    assert values["door_open"] is False
    assert values["label"] == "normal"
    assert source_ts.replace(tzinfo=UTC) == ts


def test_setpoint_written_by_client_reaches_the_controller():
    async def scenario(new_value):
        space = await stub_space()
        controller = HysteresisController(CONFIG.controller)
        await space.setpoint.write_value(ua.Variant(new_value, ua.VariantType.Double))
        await apply_setpoint(space, controller)
        return controller.params.setpoint_c, await space.setpoint.read_value()

    assert asyncio.run(scenario(-25.0)) == (-25.0, -25.0)


def test_out_of_range_setpoint_is_rejected_and_reset():
    async def scenario():
        space = await stub_space()
        controller = HysteresisController(replace(CONFIG.controller, setpoint_c=-18.0))
        await space.setpoint.write_value(ua.Variant(50.0, ua.VariantType.Double))
        await apply_setpoint(space, controller)
        return controller.params.setpoint_c, await space.setpoint.read_value()

    assert asyncio.run(scenario()) == (-18.0, -18.0)
