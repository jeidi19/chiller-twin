"""Simulation configuration, loaded from YAML files in ``configs/``."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ChillerParams:
    """Physical parameters of the chiller and its load (SI units, temperatures in °C)."""

    ambient_temp_c: float
    cell_heat_capacity_j_per_k: float
    product_heat_capacity_j_per_k: float
    ua_env_w_per_k: float
    ua_product_w_per_k: float
    ua_door_w_per_k: float
    cooling_capacity_w: float
    compressor_power_w: float


@dataclass(frozen=True)
class ControllerParams:
    setpoint_c: float
    hysteresis_c: float
    min_on_time_s: float
    min_off_time_s: float


@dataclass(frozen=True)
class InitialState:
    cell_temp_c: float
    product_temp_c: float


@dataclass(frozen=True)
class DoorEvent:
    start_s: float
    duration_s: float


@dataclass(frozen=True)
class FaultSpec:
    """A fault that starts at ``start_s`` and ramps linearly to ``max_severity`` (0..1)."""

    kind: str
    start_s: float
    ramp_s: float
    max_severity: float = 1.0


@dataclass(frozen=True)
class SimulationConfig:
    chiller: ChillerParams
    controller: ControllerParams
    initial: InitialState
    duration_s: float
    dt_s: float = 1.0
    sample_period_s: float = 10.0
    sensor_noise_c: float = 0.1
    seed: int = 42
    door_events: tuple[DoorEvent, ...] = field(default_factory=tuple)
    faults: tuple[FaultSpec, ...] = field(default_factory=tuple)


def load_config(path: str | Path) -> SimulationConfig:
    raw = yaml.safe_load(Path(path).read_text())
    sim = raw.get("simulation", {})
    return SimulationConfig(
        chiller=ChillerParams(**raw["chiller"]),
        controller=ControllerParams(**raw["controller"]),
        initial=InitialState(**raw["initial"]),
        door_events=tuple(DoorEvent(**e) for e in raw.get("door_events", [])),
        faults=tuple(FaultSpec(**f) for f in raw.get("faults", [])),
        **sim,
    )
