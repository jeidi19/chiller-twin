import numpy as np
import pytest

from simulator.config import ChillerParams, FaultSpec
from simulator.faults import active_label, apply_faults, measure_cell_temp, severity

PARAMS = ChillerParams(
    ambient_temp_c=25.0,
    cell_heat_capacity_j_per_k=50_000.0,
    product_heat_capacity_j_per_k=70_000.0,
    ua_env_w_per_k=15.0,
    ua_product_w_per_k=30.0,
    ua_door_w_per_k=150.0,
    cooling_capacity_w=5_000.0,
    compressor_power_w=2_000.0,
)


def test_severity_ramp():
    f = FaultSpec("refrigerant_leak", start_s=100, ramp_s=100, max_severity=0.8)
    assert severity(f, 50) == 0.0
    assert severity(f, 150) == pytest.approx(0.4)
    assert severity(f, 1_000) == pytest.approx(0.8)


def test_no_faults_leaves_params_unchanged():
    assert apply_faults(PARAMS, (), 1_000) == PARAMS


def test_fault_signatures_differ():
    t = 10_000
    leak = apply_faults(PARAMS, (FaultSpec("refrigerant_leak", 0, 0),), t)
    wear = apply_faults(PARAMS, (FaultSpec("compressor_wear", 0, 0),), t)
    gasket = apply_faults(PARAMS, (FaultSpec("door_gasket", 0, 0),), t)

    assert leak.cooling_capacity_w < PARAMS.cooling_capacity_w
    assert leak.compressor_power_w < PARAMS.compressor_power_w
    assert wear.compressor_power_w > PARAMS.compressor_power_w
    assert gasket.ua_env_w_per_k > PARAMS.ua_env_w_per_k
    assert gasket.cooling_capacity_w == PARAMS.cooling_capacity_w


def test_sensor_drift_only_affects_measurement():
    faults = (FaultSpec("sensor_drift", 0, 0),)
    assert apply_faults(PARAMS, faults, 100) == PARAMS
    rng = np.random.default_rng(0)
    assert measure_cell_temp(-18.0, faults, 100, noise_c=0.0, rng=rng) == pytest.approx(-15.0)


def test_unknown_fault_kind_raises():
    with pytest.raises(ValueError):
        apply_faults(PARAMS, (FaultSpec("gremlins", 0, 0),), 10)


def test_labels():
    faults = (FaultSpec("compressor_wear", start_s=100, ramp_s=10),)
    assert active_label(faults, 50) == "normal"
    assert active_label(faults, 105) == "compressor_wear"
