"""OPC UA information model of the blast chiller: which nodes a client sees.

>>> TODO (Jacopo): implement ``build_address_space()``. It is the OPC UA equivalent of
>>> choosing the variables of a Carel controller: names, types, units and what a remote
>>> client may change. The tests in ``tests/test_opcua_model.py`` are ``xfail`` and
>>> start passing when it is done (then remove their ``pytestmark``).

Contract (the server, the gateway and the tests rely on it):

- one Object with BrowseName ``Chiller`` under the standard ``Objects`` folder;
- for every name in ``TELEMETRY_FIELDS`` one Variable *somewhere below* ``Chiller``
  (you choose the folders) whose BrowseName is exactly that name, in namespace ``idx``;
- data types: ``Double`` for temperatures and power, ``Boolean`` for ``compressor_on``
  and ``door_open``, ``String`` for ``label``;
- telemetry is read-only for clients;
- one writable ``Double`` Variable for the controller setpoint (°C), initialised with
  ``config.controller.setpoint_c``: the server applies what a client writes there.

Useful asyncua calls (all awaited): ``parent.add_object(idx, name)``,
``parent.add_folder(idx, name)``, ``parent.add_variable(idx, name, value,
varianttype=ua.VariantType.Double)``, ``node.set_writable()``,
``node.add_property(...)``. Start from ``server.nodes.objects``.

Questions worth thinking about (interviewers ask them):
- Why expose an OPC UA *model* (objects, folders, types) instead of a flat list of
  tags like Modbus registers? What does a client gain from browsing it?
- How would you publish engineering units (``EUInformation``) and value ranges?
- Which values should a remote client be allowed to write, and what must the server
  check before accepting them (range, permissions, machine state)?
- ``label`` is ground truth that a real machine would not know: is it right to put it
  in the address space? How would you separate it in a real plant?
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncua import Node, Server

from simulator.config import SimulationConfig

NAMESPACE_URI = "urn:chiller-twin:blast-chiller"


@dataclass(frozen=True)
class AddressSpace:
    """Nodes the server writes to (telemetry) and reads from (setpoint)."""

    telemetry: dict[str, Node]  # one entry per name in TELEMETRY_FIELDS
    setpoint: Node


async def build_address_space(server: Server, idx: int, config: SimulationConfig) -> AddressSpace:
    """Create the chiller nodes in namespace ``idx`` and return them."""
    raise NotImplementedError("OPC UA information model not implemented yet: see the docstring.")
