"""OPC UA information model of the blast chiller: which nodes a client sees.

The machine is one Object, ``Chiller``, under the standard ``Objects`` folder. Clients
find its variables by browsing it, so they need no fixed addresses as with Modbus
registers.

Contract (the server, the gateway and the tests rely on it):

- for every name in ``TELEMETRY_FIELDS`` one Variable below ``Chiller`` whose
  BrowseName is exactly that name, in namespace ``idx`` (the gateway matches by name,
  also inside sub-folders);
- data types: ``Double`` for temperatures (including ``active_setpoint_c``) and power,
  ``Boolean`` for ``compressor_on`` and ``door_open``, ``String`` for ``label``;
- telemetry is read-only for clients;
- ``setpoint_c`` is the only writable node: the setpoint *command* (°C), initialised
  with ``config.controller.setpoint_c``.

Design notes:

- Requested vs actual value: ``setpoint_c`` is what a client asks for,
  ``active_setpoint_c`` is what the controller is using. The server applies a request
  only if it is in range (``opcua_server.apply_setpoint``); otherwise it resets the
  command to the active value, so a client can see that the write was rejected.
- ``label`` is ground truth that only exists because this is a simulation: a real
  machine does not know it has a fault. In a plant, labels come from maintenance
  records and are joined with the data later.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncua import Node, Server, ua

from simulator.config import SimulationConfig

NAMESPACE_URI = "urn:chiller-twin:blast-chiller"


@dataclass(frozen=True)
class AddressSpace:
    """Nodes the server writes to (telemetry) and reads from (setpoint)."""

    telemetry: dict[str, Node]  # one entry per name in TELEMETRY_FIELDS
    setpoint: Node


async def build_address_space(server: Server, idx: int, config: SimulationConfig) -> AddressSpace:
    """Create the chiller nodes in namespace ``idx`` and return them."""
    machine = await server.nodes.objects.add_object(idx, "Chiller")
    measurements = await machine.add_folder(idx, "Measurements")
    status = await machine.add_folder(idx, "Status")
    parameters = await machine.add_folder(idx, "Parameters")
    active_setpoint = await status.add_variable(
        idx, "active_setpoint_c", config.controller.setpoint_c, varianttype=ua.VariantType.Double
    )
    cell_temp = await measurements.add_variable(
        idx, "cell_temp_c", 0.0, varianttype=ua.VariantType.Double
    )
    product_temp = await measurements.add_variable(
        idx, "product_temp_c", 0.0, varianttype=ua.VariantType.Double
    )
    compressor_on = await status.add_variable(
        idx, "compressor_on", False, varianttype=ua.VariantType.Boolean
    )
    door_open = await status.add_variable(
        idx, "door_open", False, varianttype=ua.VariantType.Boolean
    )
    compressor_power = await measurements.add_variable(
        idx, "compressor_power_w", 0.0, varianttype=ua.VariantType.Double
    )
    label = await machine.add_variable(idx, "label", "", varianttype=ua.VariantType.String)
    setpoint = await parameters.add_variable(
        idx, "setpoint_c", config.controller.setpoint_c, varianttype=ua.VariantType.Double
    )
    await setpoint.set_writable()
    return AddressSpace(
        telemetry={
            "active_setpoint_c": active_setpoint,
            "cell_temp_c": cell_temp,
            "product_temp_c": product_temp,
            "compressor_on": compressor_on,
            "door_open": door_open,
            "compressor_power_w": compressor_power,
            "label": label,
        },
        setpoint=setpoint,
    )
