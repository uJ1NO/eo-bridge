"""Optical components for the bridge.

Two backends live behind the same interface:

* MachZehnderModulator (this file) - the analytical cos^2 transfer
  function.  Fast, dependency-free, perfectly differentiable.  This is
  the default.

* SimphonyMZI (eo_bridge.simphony_backend) - a real Mach-Zehnder built
  from Simphony / sax photonic primitives.  Slower per call, but it's
  the same code path you'd use to validate against a foundry PDK.

The bridge only needs `simulate(V) -> (P_out_w, V_fb_v)` so either one
plugs in.
"""

import math
import random
from dataclasses import dataclass


@dataclass
class MachZehnderModulator:
    """Balanced push-pull MZM. Bright at V=0, dark at V=V_pi.

    T(V) = cos^2( pi * V / (2 * V_pi) )

    This is the same transfer function Simphony arrives at numerically
    when you wire two 50/50 couplers around two waveguides and push one
    arm by phi = pi * V / V_pi.  We have a test for that.
    """
    v_pi: float = 1.2
    insertion_loss_db: float = 3.0      # passive loss of the device
    extinction_ratio_db: float = 25.0   # finite extinction floor

    def transmit(self, p_in_w, voltage):
        if p_in_w < 0:
            raise ValueError("p_in_w must be >= 0")
        ideal = math.cos(math.pi * voltage / (2.0 * self.v_pi)) ** 2

        # Real devices never reach a true zero. Clamp at the spec ER.
        floor = 10 ** (-self.extinction_ratio_db / 10.0)
        t = max(ideal, floor)
        t *= 10 ** (-self.insertion_loss_db / 10.0)
        return p_in_w * t


@dataclass
class Photodetector:
    """Ge-on-Si PD + transimpedance amplifier returning a voltage."""
    responsivity_a_per_w: float = 0.8
    transimpedance_ohm: float = 2.0e3
    dark_current_a: float = 5e-9
    noise_rms_v: float = 1e-3
    # NOTE: noise is purely input-referred Gaussian here. A real PD has
    # shot noise that scales with sqrt(I_photo). Good enough for an MVP.

    _rng: random.Random = None

    def __post_init__(self):
        if self._rng is None:
            self._rng = random.Random(42)

    def detect(self, p_opt_w):
        i = self.responsivity_a_per_w * p_opt_w + self.dark_current_a
        v = i * self.transimpedance_ohm
        v += self._rng.gauss(0.0, self.noise_rms_v)
        return v


@dataclass
class OpticalLink:
    """Composes laser + modulator + detector into one `simulate(V)` call.

    Pass in any object exposing `transmit(p_in_w, voltage) -> p_out_w` as
    `modulator` and you've swapped backends without touching the bridge.
    """
    laser_power_w: float = 1.0e-3
    modulator: object = None
    detector: Photodetector = None

    def __post_init__(self):
        if self.modulator is None:
            self.modulator = MachZehnderModulator()
        if self.detector is None:
            self.detector = Photodetector()

    def simulate(self, voltage):
        p_out = self.modulator.transmit(self.laser_power_w, voltage)
        v_fb = self.detector.detect(p_out)
        return p_out, v_fb
