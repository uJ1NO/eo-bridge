"""Drop-in MZM backend built on top of Simphony / sax.

Why: the analytical MZM in `optical_sim.py` is exact for an ideal device.
Real silicon photonics has dispersion, finite directional-coupler ratios,
waveguide loss per cm, and so on.  Simphony lets you plug any of that in
without leaving Python.

Usage:

    from eo_bridge import OpticalLink, Photodetector
    from eo_bridge.simphony_backend import SimphonyMZI

    link = OpticalLink(
        laser_power_w=1e-3,
        modulator=SimphonyMZI(v_pi=1.2),
        detector=Photodetector(),
    )
    p_out, v_fb = link.simulate(0.6)   # same interface as the analytical one

We use sax (which is what Simphony 0.7+ is built on) to compose two
50/50 couplers around two waveguides.  The modulator drives one arm's
effective length to produce phi = pi * V / V_pi.
"""

import math

try:
    import sax
    import simphony.libraries.ideal as ideal
    _AVAILABLE = True
except Exception as exc:                # pragma: no cover
    _AVAILABLE = False
    _IMPORT_ERR = exc


class SimphonyMZI:
    """Mach-Zehnder modulator built from Simphony primitives.

    Same `transmit(p_in_w, voltage) -> p_out_w` interface as the
    analytical model so it slots into OpticalLink without changes.
    """

    def __init__(self, v_pi=1.2, n_eff=2.34, n_group=3.4,
                 arm_length_um=10.0, wavelength_um=1.55,
                 insertion_loss_db=3.0):
        if not _AVAILABLE:
            raise ImportError(
                "Simphony/sax not installed. Run `pip install simphony` "
                f"(import error: {_IMPORT_ERR})"
            )
        self.v_pi = v_pi
        self.n_eff = n_eff
        self.n_group = n_group
        self.arm_length_um = arm_length_um
        self.wavelength_um = wavelength_um
        self.insertion_loss_db = insertion_loss_db

        # delta_L_per_volt such that V=V_pi gives a pi phase shift.
        # From phi = 2*pi*n_eff*delta_L/lambda the required delta_L
        # equals lambda / (2*n_eff) at V = V_pi.
        self._dL_per_volt = (wavelength_um / (2.0 * n_eff)) / v_pi

        # Build the sax circuit once. Each call to .transmit reuses it.
        self._mzi, _ = sax.circuit(
            netlist={
                "instances": {
                    "c1":  "coupler",
                    "top": "waveguide",
                    "bot": "waveguide",
                    "c2":  "coupler",
                },
                "connections": {
                    "c1,o1":  "top,o0",
                    "c1,o3":  "bot,o0",
                    "top,o1": "c2,o0",
                    "bot,o1": "c2,o2",
                },
                "ports": {
                    "in":  "c1,o0",
                    "bar": "c2,o3",   # bright at V=0, like our analytical MZM
                },
            },
            models={"coupler": ideal.coupler, "waveguide": ideal.waveguide},
        )

    # -------- main interface ---------------------------------------------------
    def transmit(self, p_in_w, voltage):
        if p_in_w < 0:
            raise ValueError("p_in_w must be >= 0")

        L_top = self.arm_length_um + self._dL_per_volt * voltage
        s = self._mzi(
            top={"length": L_top, "neff": self.n_eff, "ng": self.n_group,
                 "wl": self.wavelength_um, "wl0": self.wavelength_um},
            bot={"length": self.arm_length_um, "neff": self.n_eff,
                 "ng": self.n_group, "wl": self.wavelength_um,
                 "wl0": self.wavelength_um},
        )
        t = float(abs(s[("in", "bar")]) ** 2)
        t *= 10 ** (-self.insertion_loss_db / 10.0)
        return p_in_w * t
