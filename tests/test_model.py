"""Behavioural spec of the thermal model.

These tests describe what model.step() must do. They are xfail until the model is
implemented: when they pass, remove the ``pytestmark`` line below.
"""

from dataclasses import replace

import pytest

from simulator.model import PlantInputs, PlantState, step
from tests.test_faults import PARAMS

COLD = PlantState(cell_temp_c=-18.0, product_temp_c=-18.0)
ON = PlantInputs(compressor_on=True, door_open=False)
OFF = PlantInputs(compressor_on=False, door_open=False)


def simulate(state, inputs, seconds, params=PARAMS):
    for _ in range(int(seconds)):
        out = step(state, inputs, params, 1.0)
        state = out.state
    return out


def test_cell_warms_when_compressor_off():
    assert simulate(COLD, OFF, 600).state.cell_temp_c > COLD.cell_temp_c


def test_cell_cools_when_compressor_on():
    warm = PlantState(cell_temp_c=0.0, product_temp_c=0.0)
    assert simulate(warm, ON, 600).state.cell_temp_c < warm.cell_temp_c


def test_open_door_warms_faster():
    door_open = replace(OFF, door_open=True)
    assert (
        simulate(COLD, door_open, 60).state.cell_temp_c > simulate(COLD, OFF, 60).state.cell_temp_c
    )


def test_product_approaches_cell_temperature_without_overshoot():
    hot = PlantState(cell_temp_c=-18.0, product_temp_c=70.0)
    out = simulate(hot, ON, 3_600)
    assert out.state.product_temp_c < 70.0
    assert out.state.product_temp_c >= out.state.cell_temp_c


def test_power_only_when_running():
    assert step(COLD, OFF, PARAMS, 1.0).compressor_power_w == 0.0
    assert step(COLD, ON, PARAMS, 1.0).compressor_power_w == pytest.approx(
        PARAMS.compressor_power_w
    )


def test_hard_chill_cycle_reaches_3c_core_within_90_minutes():
    """Blast chillers are rated by how fast they bring the product core to +3 °C."""
    from pathlib import Path

    from simulator.config import load_config
    from simulator.simulation import run

    config = load_config(Path(__file__).parent.parent / "configs" / "default.yaml")
    records = run(replace(config, door_events=()))
    reached = [r["t_s"] for r in records if r["product_temp_c"] <= 3.0]
    assert reached and reached[0] <= 90 * 60
