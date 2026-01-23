"""Virtual Bus - A modular CAN traffic simulation and analysis framework."""

__version__ = "0.1.0"

from virtual_bus.core.frame import CANFrame
from virtual_bus.core.bus import VirtualCANBus
from virtual_bus.core.node import CANNode
from virtual_bus.observer.observer import BusObserver
from virtual_bus.normalizer.normalizer import FrameNormalizer
from virtual_bus.analyzer.analyzer import TimingAnalyzer
from virtual_bus.recorder.recorder import TrafficRecorder
from virtual_bus.recorder.player import TrafficPlayer

__all__ = [
    "CANFrame",
    "VirtualCANBus",
    "CANNode",
    "BusObserver",
    "FrameNormalizer",
    "TimingAnalyzer",
    "TrafficRecorder",
    "TrafficPlayer",
]
