"""Unit tests for the translation layer.

Kept dependency-free (plain ``assert`` + ``__main__``) so the test runs
without ``pytest`` being installed.
"""

import math
import os
import sys

# Make ``eo_bridge`` importable when this file is executed directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eo_bridge.translator import PhysicalConstants, Translator


def test_logic_state_to_voltage_endpoints() -> None:
    t = Translator(register_width=8)
    assert t.logic_state_to_voltage(0) == 0.0
    assert math.isclose(t.logic_state_to_voltage(255), 1.2, rel_tol=1e-9)


def test_voltage_to_phase_at_vpi_is_pi() -> None:
    t = Translator(PhysicalConstants(v_pi=1.2))
    assert math.isclose(t.voltage_to_phase_shift(1.2), math.pi, rel_tol=1e-12)


def test_wavelength_shift_scales_linearly() -> None:
    t = Translator()
    a = t.voltage_to_wavelength_shift(0.5)
    b = t.voltage_to_wavelength_shift(1.0)
    assert math.isclose(b, 2.0 * a, rel_tol=1e-12)


def test_optical_voltage_to_enable_threshold() -> None:
    t = Translator(PhysicalConstants(feedback_threshold_v=0.4))
    assert t.optical_voltage_to_enable(0.0) == 0
    assert t.optical_voltage_to_enable(0.4) == 0  # strictly greater than
    assert t.optical_voltage_to_enable(0.5) == 1


def test_state_out_of_range_rejected() -> None:
    t = Translator(register_width=4)
    try:
        t.logic_state_to_voltage(16)
    except ValueError:
        return
    raise AssertionError("expected ValueError for out-of-range state")


def main() -> int:
    tests = [
        test_logic_state_to_voltage_endpoints,
        test_voltage_to_phase_at_vpi_is_pi,
        test_wavelength_shift_scales_linearly,
        test_optical_voltage_to_enable_threshold,
        test_state_out_of_range_rejected,
    ]
    for fn in tests:
        fn()
        print(f"PASS  {fn.__name__}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
