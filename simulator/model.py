"""Thermal model of the blast chiller.

Two lumped thermal masses (cell air + product core), integrated with explicit Euler:

    Q_env     = UA_env  * (T_amb  - T_cell)                 heat entering through walls
    Q_door    = UA_door * (T_amb  - T_cell) if door open    heat entering through the door
    Q_product = UA_prod * (T_prod - T_cell)                 heat released by the product
    Q_cool    = cooling_capacity if compressor on else 0    heat removed by the evaporator

    dT_cell/dt = (Q_env + Q_door + Q_product - Q_cool) / C_cell
    dT_prod/dt = -Q_product / C_prod

    power = compressor_power if compressor on else 0

Numerical stability: the fastest time constant is tau = C_cell / (UA_env + UA_door +
UA_prod), about 256 s with ``configs/default.yaml``. Explicit Euler is stable for
dt < 2 * tau, so dt = 1 s is both stable and accurate.

Known limitations (possible extensions):
- Q_cool is constant, while real capacity drops as the evaporating temperature falls;
  a next step is Q_cool = UA_evap * (T_cell - T_evap).
- The product is a single node (no core/surface gradient).
- No evaporator thermal mass, icing or defrost cycles.
"""

from __future__ import annotations

from dataclasses import dataclass

from simulator.config import ChillerParams


@dataclass(frozen=True)
class PlantState:
    cell_temp_c: float
    product_temp_c: float


@dataclass(frozen=True)
class PlantInputs:
    compressor_on: bool
    door_open: bool


@dataclass(frozen=True)
class PlantOutputs:
    state: PlantState
    compressor_power_w: float


def step(
    state: PlantState, inputs: PlantInputs, params: ChillerParams, dt_s: float
) -> PlantOutputs:
    """Advance the plant by ``dt_s`` seconds."""
    compressor_power_w = params.compressor_power_w if inputs.compressor_on else 0.0

    Q_env = params.ua_env_w_per_k * (params.ambient_temp_c - state.cell_temp_c)
    if inputs.door_open:
        Q_door = params.ua_door_w_per_k * (params.ambient_temp_c - state.cell_temp_c)
    else:
        Q_door = 0.0

    Q_product = params.ua_product_w_per_k * (state.product_temp_c - state.cell_temp_c)
    Q_cool = params.cooling_capacity_w if inputs.compressor_on else 0.0

    dT_cell = (Q_env + Q_door + Q_product - Q_cool) / params.cell_heat_capacity_j_per_k
    dT_prod = -Q_product / params.product_heat_capacity_j_per_k

    new_cell_temp = state.cell_temp_c + dT_cell * dt_s
    new_product_temp = state.product_temp_c + dT_prod * dt_s
    return PlantOutputs(
        state=PlantState(new_cell_temp, new_product_temp), compressor_power_w=compressor_power_w
    )
