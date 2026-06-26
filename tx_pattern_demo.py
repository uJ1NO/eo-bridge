"""End-to-end demo: send a byte through the optical link and recover it.

The signal path mirrors a real photonic transceiver (chip-to-chip
optical interconnect):

    digital bits -> driver -> MZM -> waveguide -> photodiode -> TIA ->
    slicer -> recovered bits

PyRTL provides the digital side (ROM-backed bit serializer). The optical
link uses the analytical MZM + Ge-on-Si PD from optical_sim.py. Each bit
is oversampled by a few clock ticks so the receiver sees a small eye
that can be plotted.

Run:

    python tx_pattern_demo.py

Outputs:

    tx_pattern_demo.png   - 3-panel scope-style figure
    stdout                - bit-by-bit table + BER summary
"""

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eo_bridge import (
    ElectricalTransmitter,
    MachZehnderModulator,
    OpticalLink,
    Photodetector,
)


# ASCII byte 0x45 = 0b01000101. Has a mix of runs and transitions, which
# makes the eye opening and the bit-error rate easier to read off the
# generated figure.
MESSAGE_BYTE = 0x45
SAMPLES_PER_BIT = 8

PLOT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "tx_pattern_demo.png")


def byte_to_bits(byte, n=8):
    """Return MSB-first list of N bits."""
    return [(byte >> (n - 1 - i)) & 1 for i in range(n)]


def run():
    tx_bits = byte_to_bits(MESSAGE_BYTE)
    print(f"TX byte: 0x{MESSAGE_BYTE:02X}")
    print(f"TX bits: {tx_bits}\n")

    # --- electrical TX (PyRTL ROM + counter walks the pattern) ----------------
    tx = ElectricalTransmitter(tx_bits, repeat=False)

    # --- optical link ---------------------------------------------------------
    link = OpticalLink(
        laser_power_w=1.0e-3,
        modulator=MachZehnderModulator(v_pi=1.2,
                                       insertion_loss_db=3.0,
                                       extinction_ratio_db=20.0),
        # Bump the noise a little so the eye actually looks like an eye.
        detector=Photodetector(noise_rms_v=8e-3),
    )

    # 1-bit DAC: bit=1 -> 0 V (bright), bit=0 -> V_pi (dark). The bright
    # symbol is mapped to logic 1 so the photocurrent and the recovered
    # bit have the same polarity, which keeps the slicer threshold
    # straightforward to interpret on the plot.
    drive_hi = 0.0   # bright optical level (bit = 1)
    drive_lo = 1.2   # V_pi gives dark optical level (bit = 0)

    # Oversampling: each transmitted bit is held for SAMPLES_PER_BIT clock
    # ticks at the optical link. The PyRTL ROM only advances its address
    # on the last sub-tick of a bit window (enable=1); on the other ticks
    # we hold (enable=0) so the same bit drives the modulator across the
    # whole window. This mirrors how a DAC/PHY oversamples a bit for
    # transmission.
    samples = []
    for bit_idx in range(len(tx_bits)):
        for sub in range(SAMPLES_PER_BIT):
            advance = 1 if sub == SAMPLES_PER_BIT - 1 else 0
            bit, addr = tx.step(enable=advance)
            v_drive = drive_hi if bit == 1 else drive_lo
            p_opt, v_fb = link.simulate(v_drive)
            samples.append({
                "tick": bit_idx * SAMPLES_PER_BIT + sub,
                "bit_idx": bit_idx,
                "tx_bit": bit,
                "v_drive": v_drive,
                "p_opt_uw": p_opt * 1e6,
                "v_fb": v_fb,
            })

    # --- receiver: slice the V_fb stream at the middle of each bit ------------
    # Set the threshold halfway between the mean of bright samples and the
    # mean of dark samples (a simple, CDR-free slicer).
    bright = [s["v_fb"] for s in samples if s["tx_bit"] == 1]
    dark = [s["v_fb"] for s in samples if s["tx_bit"] == 0]
    threshold = 0.5 * (sum(bright) / len(bright) + sum(dark) / len(dark))

    rx_bits = []
    for bit_idx in range(len(tx_bits)):
        # Sample at the centre tick of each bit.
        centre_tick = bit_idx * SAMPLES_PER_BIT + SAMPLES_PER_BIT // 2
        v = samples[centre_tick]["v_fb"]
        rx_bits.append(1 if v > threshold else 0)

    errors = sum(1 for a, b in zip(tx_bits, rx_bits) if a != b)
    ber = errors / len(tx_bits)

    print(f"slicer threshold: {threshold * 1e3:.1f} mV\n")
    print(f"{'idx':>3}  {'tx':>2}  {'rx':>2}  {'V_fb_centre[mV]':>16}  {'ok':>3}")
    print("-" * 40)
    for i, (a, b) in enumerate(zip(tx_bits, rx_bits)):
        centre = samples[i * SAMPLES_PER_BIT + SAMPLES_PER_BIT // 2]["v_fb"]
        print(f"{i:>3}  {a:>2}  {b:>2}  {centre*1e3:>16.2f}  "
              f"{'OK' if a == b else 'ERR':>3}")
    rx_byte = sum(b << (7 - i) for i, b in enumerate(rx_bits))
    print(f"\nRX byte: 0x{rx_byte:02X}  "
          f"errors={errors}/{len(tx_bits)}  BER={ber:.2g}")

    plot(samples, threshold, tx_bits, rx_bits)
    print(f"\nWrote {PLOT_PATH}")

    return errors


def plot(samples, threshold, tx_bits, rx_bits):
    ticks = [s["tick"] for s in samples]
    v_drive = [s["v_drive"] for s in samples]
    p_opt = [s["p_opt_uw"] for s in samples]
    v_fb = [s["v_fb"] * 1e3 for s in samples]
    bit_edges = [i * SAMPLES_PER_BIT for i in range(len(tx_bits) + 1)]

    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)

    ax0 = axes[0]
    ax0.set_title("Optical link: 0x45 transmitted through MZM and photodiode")
    ax0.step(ticks, v_drive, where="post", color="tab:blue")
    ax0.set_ylabel("MZM drive (V)")
    ax0.set_ylim(-0.15, 1.35)
    for x in bit_edges:
        ax0.axvline(x, color="0.85", linewidth=0.8)
    for i, b in enumerate(tx_bits):
        ax0.text(i * SAMPLES_PER_BIT + SAMPLES_PER_BIT / 2,
                 1.22, str(b), ha="center", va="center",
                 color="tab:blue", fontsize=10, fontweight="bold")

    ax1 = axes[1]
    ax1.plot(ticks, p_opt, color="tab:red")
    ax1.set_ylabel("Optical out (µW)")
    for x in bit_edges:
        ax1.axvline(x, color="0.85", linewidth=0.8)

    ax2 = axes[2]
    ax2.plot(ticks, v_fb, color="tab:green", label="TIA voltage")
    ax2.axhline(threshold * 1e3, color="k", linestyle="--",
                linewidth=1, label=f"slicer @ {threshold*1e3:.0f} mV")
    ax2.set_ylabel("RX TIA (mV)")
    ax2.set_xlabel("Clock tick (8 ticks per transmitted bit)")
    for x in bit_edges:
        ax2.axvline(x, color="0.85", linewidth=0.8)
    for i, b in enumerate(rx_bits):
        ax2.text(i * SAMPLES_PER_BIT + SAMPLES_PER_BIT / 2,
                 max(v_fb) * 1.05, str(b), ha="center", va="center",
                 color="tab:green", fontsize=10, fontweight="bold")
    ax2.legend(loc="upper right")

    fig.tight_layout()
    fig.savefig(PLOT_PATH, dpi=140)
    plt.close(fig)


if __name__ == "__main__":
    sys.exit(0 if run() == 0 else 1)
