"""Compressor controller: on/off thermostat with hysteresis and anti short-cycle timers.

Same logic you would write in a PLC: the compressor must not restart too soon after
stopping (and vice versa), otherwise it wears out.
"""

from __future__ import annotations

from dataclasses import dataclass

from simulator.config import ControllerParams


@dataclass
class HysteresisController:
    params: ControllerParams
    compressor_on: bool = False
    _time_in_state_s: float = float("inf")

    def update(self, measured_cell_temp_c: float, dt_s: float) -> bool:
        """Advance the controller by ``dt_s`` and return the compressor command."""
        self._time_in_state_s += dt_s
        p = self.params
        upper = p.setpoint_c + p.hysteresis_c / 2
        lower = p.setpoint_c - p.hysteresis_c / 2

        if not self.compressor_on:
            if measured_cell_temp_c > upper and self._time_in_state_s >= p.min_off_time_s:
                self._switch(True)
        elif measured_cell_temp_c < lower and self._time_in_state_s >= p.min_on_time_s:
            self._switch(False)
        return self.compressor_on

    def _switch(self, on: bool) -> None:
        self.compressor_on = on
        self._time_in_state_s = 0.0
