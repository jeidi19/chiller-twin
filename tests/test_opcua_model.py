"""Behavioural spec of the OPC UA information model (simulator/opcua_model.py).

xfail until build_address_space() is implemented: then remove the ``pytestmark`` line.
"""

import asyncio
from pathlib import Path

import pytest
from asyncua import Server, ua

from simulator.config import load_config
from simulator.opcua_model import NAMESPACE_URI, build_address_space
from simulator.simulation import TELEMETRY_FIELDS

pytestmark = pytest.mark.xfail(raises=NotImplementedError, strict=True)

CONFIG = load_config(Path(__file__).parent.parent / "configs" / "default.yaml")

EXPECTED_TYPES = {
    "cell_temp_c": ua.VariantType.Double,
    "product_temp_c": ua.VariantType.Double,
    "compressor_on": ua.VariantType.Boolean,
    "compressor_power_w": ua.VariantType.Double,
    "door_open": ua.VariantType.Boolean,
    "label": ua.VariantType.String,
}


async def build():
    server = Server()
    await server.init()
    idx = await server.register_namespace(NAMESPACE_URI)
    space = await build_address_space(server, idx, CONFIG)
    return server, idx, space


async def descendants(node):
    """All nodes below ``node`` (hierarchical references), depth first."""
    found = []
    for child in await node.get_children():
        found.append(child)
        found.extend(await descendants(child))
    return found


async def can_write(node) -> bool:
    access = await node.read_attribute(ua.AttributeIds.UserAccessLevel)
    return bool(access.Value.Value & ua.AccessLevel.CurrentWrite.mask)


def test_chiller_object_is_under_objects():
    async def scenario():
        server, idx, _ = await build()
        chiller = await server.nodes.objects.get_child(f"{idx}:Chiller")
        return await chiller.read_node_class()

    assert asyncio.run(scenario()) == ua.NodeClass.Object


def test_every_telemetry_field_is_a_variable_below_chiller():
    async def scenario():
        server, idx, space = await build()
        chiller = await server.nodes.objects.get_child(f"{idx}:Chiller")
        below = {n.nodeid for n in await descendants(chiller)}
        names = {}
        for name, node in space.telemetry.items():
            qn = await node.read_browse_name()
            names[name] = (qn.Name, qn.NamespaceIndex, node.nodeid in below)
        return idx, names

    idx, names = asyncio.run(scenario())
    assert set(names) == set(TELEMETRY_FIELDS)
    for name, (browse_name, ns, is_below) in names.items():
        assert browse_name == name
        assert ns == idx
        assert is_below, f"{name} is not below the Chiller object"


def test_telemetry_data_types():
    async def scenario():
        _, _, space = await build()
        return {
            n: await node.read_data_type_as_variant_type() for n, node in space.telemetry.items()
        }

    assert asyncio.run(scenario()) == EXPECTED_TYPES


def test_telemetry_is_read_only_and_setpoint_writable():
    async def scenario():
        _, _, space = await build()
        telemetry = {n: await can_write(node) for n, node in space.telemetry.items()}
        return telemetry, await can_write(space.setpoint)

    telemetry, setpoint = asyncio.run(scenario())
    assert not any(telemetry.values()), telemetry
    assert setpoint


def test_setpoint_starts_at_the_configured_value():
    async def scenario():
        _, _, space = await build()
        return (
            await space.setpoint.read_value(),
            await space.setpoint.read_data_type_as_variant_type(),
        )

    value, vtype = asyncio.run(scenario())
    assert value == CONFIG.controller.setpoint_c
    assert vtype == ua.VariantType.Double
