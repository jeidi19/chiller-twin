"""Tests of the simulation loop, using a toy plant so they do not depend on model.step()."""

from dataclasses import replace
from pathlib import Path

from simulator import model
from simulator.config import load_config
from simulator.simulation import RECORD_FIELDS, run

CONFIG = load_config(Path(__file__).parent.parent / "configs" / "faults_example.yaml")


def toy_step(state, inputs, params, dt_s):
    """Cell cools 0.05 °C/s with the compressor on and warms 0.02 °C/s otherwise."""
    rate = -0.05 if inputs.compressor_on else 0.02
    new_state = replace(state, cell_temp_c=state.cell_temp_c + rate * dt_s)
    power = params.compressor_power_w if inputs.compressor_on else 0.0
    return model.PlantOutputs(new_state, power)


def test_sampling_and_record_shape():
    records = run(CONFIG, step_fn=toy_step)
    expected = int(CONFIG.duration_s / CONFIG.sample_period_s) + 1
    assert len(records) == expected
    assert set(records[0]) == set(RECORD_FIELDS)


def test_closed_loop_holds_setpoint():
    records = run(CONFIG, step_fn=toy_step)
    steady = [r["cell_temp_c"] for r in records if 3_000 < r["t_s"] < 7_000]
    sp = CONFIG.controller.setpoint_c
    assert all(abs(t - sp) < 3.0 for t in steady)


def test_labels_follow_fault_schedule():
    records = run(CONFIG, step_fn=toy_step)
    fault_start = CONFIG.faults[0].start_s
    assert all(r["label"] == "normal" for r in records if r["t_s"] <= fault_start)
    assert records[-1]["label"] == "refrigerant_leak"


def test_door_events_recorded():
    records = run(CONFIG, step_fn=toy_step)
    assert any(r["door_open"] for r in records)
