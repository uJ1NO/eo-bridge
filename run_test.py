"""Integration test for the electro-optic co-simulation bridge.

Runs 10 closed-loop clock cycles using the default models and renders a
two-panel matplotlib figure showing that the electrical and optical
sides are synchronized in real time.

The test passes if (a) the loop completes without raising and (b) the
generated samples include a non-trivial transition in optical power
(i.e. the modulator actually responds to the counter).
"""

import os
import sys

import matplotlib
matplotlib.use("Agg")  # headless plotting
import matplotlib.pyplot as plt

from eo_bridge import (
    CoSimulationBridge,
    ElectricalCounter,
    MachZehnderModulator,
    OpticalLink,
    Photodetector,
    Translator,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# A 4-bit counter is wide enough to sweep the full V_pi range in ~10 cycles,
# which is what makes the closed loop visibly engage and self-arrest within
# the test horizon. Translator is matched to the same width so the DAC
# mapping covers [0, V_pi].
REGISTER_WIDTH = 4
NUM_CYCLES = 10
PLOT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "co_simulation.png")


def build_bridge() -> CoSimulationBridge:
    """Wire up a bridge with sensible defaults for the MVP demo."""
    return CoSimulationBridge(
        electrical=ElectricalCounter(width=REGISTER_WIDTH),
        optical=OpticalLink(
            laser_power_w=1.0e-3,
            modulator=MachZehnderModulator(v_pi=1.2),
            detector=Photodetector(),
        ),
        translator=Translator(register_width=REGISTER_WIDTH),
        bootstrap_enable=1,
    )


def plot(samples) -> None:
    cycles = [s.cycle for s in samples]
    voltage = [s.drive_voltage_v for s in samples]
    p_out_uw = [s.optical_power_w * 1e6 for s in samples]
    v_fb = [s.tia_voltage_v for s in samples]
    enable = [s.enable_in for s in samples]

    fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)

    ax_top = axes[0]
    ax_top.set_title("Electro-Optic Co-Simulation Bridge - 10 cycles")
    ax_top.set_ylabel("Electrical drive (V)", color="tab:blue")
    ax_top.plot(cycles, voltage, "o-", color="tab:blue", label="MZM drive voltage")
    ax_top.tick_params(axis="y", labelcolor="tab:blue")
    ax_top.grid(True, alpha=0.3)

    ax_top_r = ax_top.twinx()
    ax_top_r.set_ylabel("Optical power (µW)", color="tab:red")
    ax_top_r.plot(cycles, p_out_uw, "s--", color="tab:red", label="MZM output power")
    ax_top_r.tick_params(axis="y", labelcolor="tab:red")

    ax_bot = axes[1]
    ax_bot.set_xlabel("Clock cycle")
    ax_bot.set_ylabel("Feedback TIA (V)", color="tab:green")
    ax_bot.plot(cycles, v_fb, "o-", color="tab:green", label="Photodetector TIA")
    ax_bot.tick_params(axis="y", labelcolor="tab:green")
    ax_bot.grid(True, alpha=0.3)

    ax_bot_r = ax_bot.twinx()
    ax_bot_r.set_ylabel("Counter enable", color="tab:purple")
    ax_bot_r.step(cycles, enable, where="post", color="tab:purple",
                  linewidth=2, label="enable -> next cycle")
    ax_bot_r.set_ylim(-0.2, 1.2)
    ax_bot_r.set_yticks([0, 1])
    ax_bot_r.tick_params(axis="y", labelcolor="tab:purple")

    fig.tight_layout()
    fig.savefig(PLOT_PATH, dpi=140)
    plt.close(fig)


def main() -> int:
    bridge = build_bridge()
    samples = bridge.run(NUM_CYCLES)

    print(f"Ran {len(samples)} co-simulation cycles\n")
    header = (
        f"{'cyc':>3}  {'en_in':>5}  {'cnt':>4}  "
        f"{'V_drv':>7}  {'phi_rad':>8}  {'P_out_uW':>9}  "
        f"{'V_fb':>6}  {'en_out':>6}"
    )
    print(header)
    print("-" * len(header))
    for s in samples:
        print(
            f"{s.cycle:>3}  {s.enable_in:>5}  {s.count:>4}  "
            f"{s.drive_voltage_v:>7.4f}  {s.phase_shift_rad:>8.4f}  "
            f"{s.optical_power_w * 1e6:>9.3f}  {s.tia_voltage_v:>6.3f}  "
            f"{s.enable_out:>6}"
        )

    plot(samples)
    print(f"\nWrote plot to: {PLOT_PATH}")

    # Sanity assertions for the test harness.
    p_min = min(s.optical_power_w for s in samples)
    p_max = max(s.optical_power_w for s in samples)
    assert p_max > p_min, "optical power did not change - bridge is not synchronized"
    contrast = (p_max - p_min) / p_max
    print(f"Modulation contrast over the run: {contrast * 100:.1f} %")
    assert contrast > 0.2, "modulation contrast too low to be considered a working loop"

    return 0


if __name__ == "__main__":
    sys.exit(main())
