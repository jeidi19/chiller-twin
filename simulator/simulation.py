"""Simulation loop: plant + controller + faults, sampled like a real data logger."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from simulator import model
from simulator.config import ChillerParams, DoorEvent, SimulationConfig
from simulator.control import HysteresisController
from simulator.faults import active_label, apply_faults, measure_cell_temp

StepFn = Callable[[model.PlantState, model.PlantInputs, ChillerParams, float], model.PlantOutputs]

RECORD_FIELDS = (
    "t_s",
    "cell_temp_c",
    "product_temp_c",
    "compressor_on",
    "compressor_power_w",
    "door_open",
    "label",
)


def door_is_open(events: tuple[DoorEvent, ...], t_s: float) -> bool:
    return any(e.start_s <= t_s < e.start_s + e.duration_s for e in events)


def run(config: SimulationConfig, step_fn: StepFn = model.step) -> list[dict]:
    """Run the simulation and return one record every ``sample_period_s``.

    ``cell_temp_c`` is the *measured* value (noise + sensor faults), as a real
    machine would publish it; ``label`` is the ground truth used to train/evaluate ML.
    """
    rng = np.random.default_rng(config.seed)
    controller = HysteresisController(config.controller)
    state = model.PlantState(config.initial.cell_temp_c, config.initial.product_temp_c)

    records: list[dict] = []
    steps = int(round(config.duration_s / config.dt_s))
    sample_every = max(1, int(round(config.sample_period_s / config.dt_s)))

    for i in range(steps + 1):
        t = i * config.dt_s
        measured = measure_cell_temp(
            state.cell_temp_c, config.faults, t, config.sensor_noise_c, rng
        )
        inputs = model.PlantInputs(
            compressor_on=controller.update(measured, config.dt_s),
            door_open=door_is_open(config.door_events, t),
        )
        params = apply_faults(config.chiller, config.faults, t)
        out = step_fn(state, inputs, params, config.dt_s)

        if i % sample_every == 0:
            records.append(
                {
                    "t_s": t,
                    "cell_temp_c": round(measured, 3),
                    "product_temp_c": round(state.product_temp_c, 3),
                    "compressor_on": int(inputs.compressor_on),
                    "compressor_power_w": round(out.compressor_power_w, 1),
                    "door_open": int(inputs.door_open),
                    "label": active_label(config.faults, t),
                }
            )
        state = out.state

    return records
