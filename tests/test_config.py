from pathlib import Path

import pytest

from simulator.config import load_config
from simulator.faults import FAULT_KINDS

CONFIGS = sorted(Path(__file__).parent.parent.joinpath("configs").glob("*.yaml"))


@pytest.mark.parametrize("path", CONFIGS, ids=lambda p: p.name)
def test_shipped_configs_load(path):
    config = load_config(path)
    assert config.duration_s > 0
    assert all(f.kind in FAULT_KINDS for f in config.faults)
