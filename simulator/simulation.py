"""Simulation loop: plant + controller + faults, sampled like a real data logger."""

from __future__ import annotations

from collections.abc import Callable, Iterator

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
# What the machine publishes (OPC UA → MQTT → InfluxDB): every record field except time.
TELEMETRY_FIELDS = RECORD_FIELDS[1:]


def door_is_open(events: tuple[DoorEvent, ...], t_s: float) -> bool:
    return any(e.start_s <= t_s < e.start_s + e.duration_s for e in events)


def iter_run(
    config: SimulationConfig,
    step_fn: StepFn = model.step,
    controller: HysteresisController | None = None,
) -> Iterator[dict]:
    """Run the simulation lazily, yielding one record every ``sample_period_s``.

    ``cell_temp_c`` is the *measured* value (noise + sensor faults), as a real
    machine would publish it; ``label`` is the ground truth used to train/evaluate ML.

    Pass your own ``controller`` to change its parameters while the simulation runs
    (e.g. a setpoint written by a remote client over OPC UA).
    """
    rng = np.random.default_rng(config.seed)
    if controller is None:
        controller = HysteresisController(config.controller)
    state = model.PlantState(config.initial.cell_temp_c, config.initial.product_temp_c)

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
            yield {
                "t_s": t,
                "cell_temp_c": round(measured, 3),
                "product_temp_c": round(state.product_temp_c, 3),
                "compressor_on": int(inputs.compressor_on),
                "compressor_power_w": round(out.compressor_power_w, 1),
                "door_open": int(inputs.door_open),
                "label": active_label(config.faults, t),
            }
        state = out.state


def run(config: SimulationConfig, step_fn: StepFn = model.step) -> list[dict]:
    """Run the whole simulation and return all the records (see ``iter_run``)."""
    return list(iter_run(config, step_fn))
