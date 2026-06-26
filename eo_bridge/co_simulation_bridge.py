"""Closed-loop electro-optic co-simulation orchestration.

Each cycle reads the electrical state, translates it to a drive voltage,
runs the optical link, and feeds the photodetector voltage back into the
electrical side as the next-cycle enable. Per-cycle quantities are
captured as CycleSample records for downstream inspection and plotting.
"""

from dataclasses import dataclass, field
from typing import List

from .electrical_sim import ElectricalCounter
from .optical_sim import OpticalLink
from .translator import Translator


@dataclass(frozen=True)
class CycleSample:
    cycle: int
    enable_in: int          # enable applied at the start of the cycle
    count: int              # counter value after the cycle
    drive_voltage_v: float
    phase_shift_rad: float
    optical_power_w: float
    tia_voltage_v: float
    enable_out: int         # enable that will be fed to the next cycle


@dataclass
class CoSimulationBridge:
    electrical: ElectricalCounter = field(default_factory=ElectricalCounter)
    optical: OpticalLink = field(default_factory=OpticalLink)
    translator: Translator = field(default_factory=Translator)
    bootstrap_enable: int = 1
    samples: List[CycleSample] = field(default_factory=list)

    def _next_enable(self):
        if not self.samples:
            return self.bootstrap_enable
        return self.samples[-1].enable_out

    def run_cycle(self):
        en_in = self._next_enable()
        count = self.electrical.step(en_in)

        v_drive = self.translator.logic_state_to_voltage(count)
        d_phi = self.translator.voltage_to_phase_shift(v_drive)
        p_opt, v_fb = self.optical.simulate(v_drive)
        en_out = self.translator.optical_voltage_to_enable(v_fb)

        s = CycleSample(
            cycle=len(self.samples),
            enable_in=en_in,
            count=count,
            drive_voltage_v=v_drive,
            phase_shift_rad=d_phi,
            optical_power_w=p_opt,
            tia_voltage_v=v_fb,
            enable_out=en_out,
        )
        self.samples.append(s)
        return s

    def run(self, num_cycles):
        if num_cycles <= 0:
            raise ValueError("num_cycles must be > 0")
        for _ in range(num_cycles):
            self.run_cycle()
        return list(self.samples)
