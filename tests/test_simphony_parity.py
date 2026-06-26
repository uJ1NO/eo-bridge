"""Sanity check: the Simphony-based MZI must agree with the analytical one.

If this test ever fails, it usually means somebody changed a constant on
one side and forgot to update the other.  Run it after touching either
`optical_sim.py` or `simphony_backend.py`.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eo_bridge.optical_sim import MachZehnderModulator

try:
    from eo_bridge.simphony_backend import SimphonyMZI
except ImportError as exc:
    print(f"SKIP: simphony not available ({exc})")
    sys.exit(0)


def main():
    # Insertion loss off on both sides so we compare the pure transfer fn.
    analytical = MachZehnderModulator(v_pi=1.2, insertion_loss_db=0.0,
                                      extinction_ratio_db=80.0)
    simphony_mzi = SimphonyMZI(v_pi=1.2, n_eff=2.34, n_group=3.4,
                               wavelength_um=1.55, insertion_loss_db=0.0)

    p_in = 1e-3  # 1 mW
    voltages = [0.0, 0.3, 0.6, 0.9, 1.2]

    print(f"{'V':>5}  {'T_analytic':>12}  {'T_simphony':>12}  {'Δ':>10}")
    print("-" * 48)
    max_err = 0.0
    for v in voltages:
        t_a = analytical.transmit(p_in, v) / p_in
        t_s = simphony_mzi.transmit(p_in, v) / p_in
        delta = abs(t_a - t_s)
        max_err = max(max_err, delta)
        print(f"{v:>5.2f}  {t_a:>12.6f}  {t_s:>12.6f}  {delta:>10.2e}")

    if max_err > 1e-3:
        raise AssertionError(
            f"Simphony and analytical disagree by {max_err:.3e} - debug me"
        )
    print(f"\nmax |Δ| = {max_err:.2e}  -> OK")


if __name__ == "__main__":
    main()
