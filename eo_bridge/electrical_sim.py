"""PyRTL-based electrical side of the co-simulation.

Two tiny hardware modules:

* ElectricalCounter - N-bit counter with a gated `enable` input. The
  bridge can hand the optical feedback to that enable each cycle and
  watch the counter self-arrest.

* ElectricalTransmitter - a ROM holding a serial bit pattern, plus an
  address counter that walks it.  This is what we use for the
  transceiver demo: it streams a byte out of PyRTL, the optical link
  carries it, and a receiver on the other side recovers it.

Both classes wrap PyRTL so the orchestration code never has to touch a
`pyrtl.Simulation` directly.
"""

import pyrtl


class ElectricalCounter:
    """N-bit counter with an external enable. One cycle per `.step()`."""

    def __init__(self, width=8, name="eo_counter"):
        if width <= 0:
            raise ValueError("width must be > 0")
        self.width = width
        self.name = name

        # Fresh PyRTL block so two instances don't collide via the global state.
        pyrtl.reset_working_block()

        enable = pyrtl.Input(1, "enable")
        count = pyrtl.Register(width, "count")
        out = pyrtl.Output(width, "count_out")

        with pyrtl.conditional_assignment:
            with enable == 1:
                count.next |= count + 1
        out <<= count

        self._sim = pyrtl.Simulation()

    def step(self, enable):
        if enable not in (0, 1):
            raise ValueError("enable must be 0 or 1")
        self._sim.step({"enable": enable})
        return int(self._sim.inspect("count_out"))

    @property
    def trace(self):
        return self._sim.tracer


class ElectricalTransmitter:
    """ROM-backed serial bit source.

    The ROM holds the pattern to transmit (MSB-first by default). An
    internal address register walks it each enabled cycle. Step returns
    the current bit being driven out; the bridge converts that bit to a
    drive voltage for the modulator.
    """

    def __init__(self, pattern_bits, repeat=False):
        if not pattern_bits:
            raise ValueError("pattern_bits cannot be empty")
        if any(b not in (0, 1) for b in pattern_bits):
            raise ValueError("pattern_bits must contain only 0 or 1")

        self.pattern = list(pattern_bits)
        self.length = len(self.pattern)
        self.repeat = repeat

        # ceil(log2(length)) addr bits, minimum 1
        addr_w = max(1, (self.length - 1).bit_length())
        rom_depth = 1 << addr_w
        rom_data = self.pattern + [0] * (rom_depth - self.length)

        pyrtl.reset_working_block()

        enable = pyrtl.Input(1, "enable")
        addr = pyrtl.Register(addr_w, "addr")
        bit_out = pyrtl.Output(1, "bit_out")
        addr_out = pyrtl.Output(addr_w, "addr_out")

        rom = pyrtl.RomBlock(bitwidth=1, addrwidth=addr_w, romdata=rom_data,
                             name="tx_rom")
        current_bit = rom[addr]
        bit_out <<= current_bit
        addr_out <<= addr

        last_addr = pyrtl.Const(self.length - 1, bitwidth=addr_w)
        with pyrtl.conditional_assignment:
            with enable == 1:
                with addr == last_addr:
                    # Repeat-or-hold logic. Holding when not repeating is the
                    # easiest way to keep the simulation valid past EOF.
                    addr.next |= pyrtl.Const(0, bitwidth=addr_w) if repeat else last_addr
                with pyrtl.otherwise:
                    addr.next |= addr + 1

        self._addr_w = addr_w
        self._sim = pyrtl.Simulation()

    def step(self, enable=1):
        if enable not in (0, 1):
            raise ValueError("enable must be 0 or 1")
        self._sim.step({"enable": enable})
        bit = int(self._sim.inspect("bit_out"))
        addr = int(self._sim.inspect("addr_out"))
        return bit, addr

    @property
    def trace(self):
        return self._sim.tracer
