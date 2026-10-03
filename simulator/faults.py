"""Fault injection.

Each fault has a different "signature" on the measured signals, so that later the ML
model can not only detect *that* something is wrong but also *what*:

- ``refrigerant_leak``: cooling capacity drops a lot, compressor power drops slightly.
- ``compressor_wear``:  compressor power rises, cooling capacity drops slightly.
- ``door_gasket``:      heat leakage from the environment increases.
- ``sensor_drift``:     the cell temperature sensor reads too high (the plant is fine,
                        but the controller is fooled by the wrong measurement).
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from simulator.config import ChillerParams, FaultSpec

FAULT_KINDS = ("refrigerant_leak", "compressor_wear", "door_gasket", "sensor_drift")
NORMAL_LABEL = "normal"

MAX_SENSOR_DRIFT_C = 3.0


def severity(fault: FaultSpec, t_s: float) -> float:
    """Linear ramp from 0 at ``start_s`` to ``max_severity`` after ``ramp_s`` seconds."""
    if t_s < fault.start_s:
        return 0.0
    if fault.ramp_s <= 0:
        return fault.max_severity
    progress = min((t_s - fault.start_s) / fault.ramp_s, 1.0)
    return progress * fault.max_severity


def apply_faults(params: ChillerParams, faults: tuple[FaultSpec, ...], t_s: float) -> ChillerParams:
    """Return the effective plant parameters at time ``t_s``."""
    for fault in faults:
        s = severity(fault, t_s)
        if s == 0.0:
            continue
        match fault.kind:
            case "refrigerant_leak":
                params = replace(
                    params,
                    cooling_capacity_w=params.cooling_capacity_w * (1 - 0.6 * s),
                    compressor_power_w=params.compressor_power_w * (1 - 0.15 * s),
                )
            case "compressor_wear":
                params = replace(
                    params,
                    cooling_capacity_w=params.cooling_capacity_w * (1 - 0.1 * s),
                    compressor_power_w=params.compressor_power_w * (1 + 0.4 * s),
                )
            case "door_gasket":
                params = replace(params, ua_env_w_per_k=params.ua_env_w_per_k * (1 + 2.0 * s))
            case "sensor_drift":
                pass  # affects the measurement, not the plant: see measure_cell_temp()
            case _:
                raise ValueError(f"Unknown fault kind: {fault.kind!r}")
    return params


def measure_cell_temp(
    true_temp_c: float,
    faults: tuple[FaultSpec, ...],
    t_s: float,
    noise_c: float,
    rng: np.random.Generator,
) -> float:
    """What the cell temperature sensor reads: truth + drift + gaussian noise."""
    drift = sum(MAX_SENSOR_DRIFT_C * severity(f, t_s) for f in faults if f.kind == "sensor_drift")
    return true_temp_c + drift + rng.normal(0.0, noise_c)


def active_label(faults: tuple[FaultSpec, ...], t_s: float) -> str:
    """Ground-truth label for the ML dataset: the active fault, or ``normal``."""
    active = [f.kind for f in faults if severity(f, t_s) > 0]
    return "+".join(active) if active else NORMAL_LABEL
