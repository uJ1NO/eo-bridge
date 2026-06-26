"""Physical translation between the electrical and optical domains.

Every unit conversion used by the bridge lives here: drive voltage from
a logic state, phase shift from voltage, the small wavelength shift it
produces on the device operating point, and the threshold that turns a
photodetector voltage back into a 1-bit enable for PyRTL.

Keeping all of this in one module is deliberate. Retargeting the bridge
to a different foundry PDK should be a single-file edit.
"""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PhysicalConstants:
    """Device-level numbers for a representative 1550 nm SiP MZM.

    Defaults are rough averages from public GlobalFoundries / IMEC SiPh
    PDK datasheets.  Don't tape out a chip based on these.
    """
    v_pi: float = 1.2                  # V, half-wave voltage of the MZM
    v_swing: float = 1.2               # V, logic-high drive level (matches V_pi by design)
    lambda0_m: float = 1550e-9         # m, laser wavelength
    n_group: float = 4.2               # group index of the Si rib waveguide
    dn_per_volt: float = 1.8e-4        # plasma-dispersion EO coefficient
    feedback_threshold_v: float = 0.4  # TIA voltage above which feedback=1


# Sensible default that callers can use without thinking.
DEFAULTS = PhysicalConstants()


class Translator:
    """Bidirectional translator. Stateless apart from its constants."""

    def __init__(self, constants=None, *, register_width=8):
        if register_width <= 0:
            raise ValueError("register_width must be > 0")
        self.constants = constants or DEFAULTS
        self.register_width = register_width
        self._full_scale = (1 << register_width) - 1

    # ---- electrical -> optical ------------------------------------------------
    def logic_state_to_voltage(self, state):
        """Linear-DAC mapping: register value -> analog drive in volts."""
        if not 0 <= state <= self._full_scale:
            raise ValueError(
                f"state {state} out of range for {self.register_width}-bit register"
            )
        return (state / self._full_scale) * self.constants.v_swing

    def voltage_to_phase_shift(self, voltage):
        # Δφ = π · V / Vπ. Standard EO phase shifter formula.
        return math.pi * voltage / self.constants.v_pi

    def voltage_to_wavelength_shift(self, voltage):
        """Effective resonance wavelength shift (meters).

        Useful for ring-resonator filters downstream. Derived from
        Δλ = λ0 · Δn_eff / n_g, with Δn_eff linear in V.
        """
        dn_eff = self.constants.dn_per_volt * voltage
        return self.constants.lambda0_m * dn_eff / self.constants.n_group

    # ---- optical -> electrical ------------------------------------------------
    def optical_voltage_to_enable(self, feedback_v):
        """Threshold the photodetector voltage into a 1-bit enable flag."""
        return 1 if feedback_v > self.constants.feedback_threshold_v else 0

    # TODO(thermal): dn/dT for Si is ~1.8e-4 /K, which is the same order as
    # dn/dV at 1 V, so a 5 K thermal swing rivals a full logic transition.
    # A thermal port on the translator is required before this model can be
    # used against measurements on real silicon.
