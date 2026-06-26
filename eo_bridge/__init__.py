"""eo_bridge: electro-optic co-simulation bridge.

Most callers only need this top-level surface::

    from eo_bridge import (
        ElectricalCounter, ElectricalTransmitter,
        MachZehnderModulator, Photodetector, OpticalLink,
        Translator, CoSimulationBridge,
    )

The Simphony-backed MZM lives in `eo_bridge.simphony_backend` to keep
the heavy JAX/sax import out of the default path.
"""

from .translator import Translator, PhysicalConstants
from .electrical_sim import ElectricalCounter, ElectricalTransmitter
from .optical_sim import MachZehnderModulator, Photodetector, OpticalLink
from .co_simulation_bridge import CoSimulationBridge, CycleSample

__all__ = [
    "Translator",
    "PhysicalConstants",
    "ElectricalCounter",
    "ElectricalTransmitter",
    "MachZehnderModulator",
    "Photodetector",
    "OpticalLink",
    "CoSimulationBridge",
    "CycleSample",
]
