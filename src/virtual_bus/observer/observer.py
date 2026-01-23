"""Passive bus observer implementation."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Optional

from virtual_bus.core.frame import CANFrame
from virtual_bus.core.bus import VirtualCANBus


@dataclass
class ObservedFrame:
    """A frame with observation metadata."""
    
    frame: CANFrame
    observation_time: float
    sequence_number: int
    inter_arrival_time: Optional[float] = None


@dataclass
class MessageStatistics:
    """Statistics for a specific arbitration ID."""
    
    count: int = 0
    first_seen: Optional[float] = None
    last_seen: Optional[float] = None
    min_interval: Optional[float] = None
    max_interval: Optional[float] = None
    total_bytes: int = 0
    
    @property
    def average_interval(self) -> Optional[float]:
        """Calculate average inter-arrival time."""
        if self.count < 2 or self.first_seen is None or self.last_seen is None:
            return None
        return (self.last_seen - self.first_seen) / (self.count - 1)


class BusObserver:
    """Passively observes CAN bus traffic without modifying it.
    
    The observer collects frames, computes statistics, and can trigger
    callbacks for real-time processing. It does not inject or suppress
    any messages on the bus.
    """
    
    def __init__(
        self,
        bus: Optional[VirtualCANBus] = None,
        buffer_size: int = 10000,
    ) -> None:
        self._bus = bus
        self._buffer_size = buffer_size
        self._buffer: list[ObservedFrame] = []
        self._sequence = 0
        self._last_times: dict[int, float] = {}
        self._statistics: dict[int, MessageStatistics] = defaultdict(MessageStatistics)
        self._callbacks: list[Callable[[ObservedFrame], None]] = []
        self._start_time: Optional[float] = None
        self._is_attached = False
    
    @property
    def frame_count(self) -> int:
        """Total number of observed frames."""
        return self._sequence
    
    @property
    def buffer(self) -> list[ObservedFrame]:
        """Access the observation buffer."""
        return self._buffer.copy()
    
    @property
    def statistics(self) -> dict[int, MessageStatistics]:
        """Per-ID statistics."""
        return dict(self._statistics)
    
    @property
    def unique_ids(self) -> set[int]:
        """Set of unique arbitration IDs observed."""
        return set(self._statistics.keys())
    
    def attach(self, bus: VirtualCANBus) -> None:
        """Attach to a bus and start observing."""
        if self._is_attached:
            self.detach()
        
        self._bus = bus
        self._bus.add_observer(self._on_frame)
        self._is_attached = True
        self._start_time = time.time()
    
    def detach(self) -> None:
        """Detach from the current bus."""
        if self._bus and self._is_attached:
            self._bus.remove_observer(self._on_frame)
            self._is_attached = False
    
    def add_callback(self, callback: Callable[[ObservedFrame], None]) -> None:
        """Add a callback for each observed frame."""
        self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[ObservedFrame], None]) -> None:
        """Remove a callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def _on_frame(self, frame: CANFrame) -> None:
        """Handle an incoming frame."""
        now = time.time()
        arb_id = frame.arbitration_id
        
        inter_arrival: Optional[float] = None
        if arb_id in self._last_times:
            inter_arrival = now - self._last_times[arb_id]
        self._last_times[arb_id] = now
        
        observed = ObservedFrame(
            frame=frame,
            observation_time=now,
            sequence_number=self._sequence,
            inter_arrival_time=inter_arrival,
        )
        self._sequence += 1
        
        if len(self._buffer) >= self._buffer_size:
            self._buffer.pop(0)
        self._buffer.append(observed)
        
        stats = self._statistics[arb_id]
        stats.count += 1
        stats.total_bytes += len(frame.data)
        
        if stats.first_seen is None:
            stats.first_seen = now
        stats.last_seen = now
        
        if inter_arrival is not None:
            if stats.min_interval is None or inter_arrival < stats.min_interval:
                stats.min_interval = inter_arrival
            if stats.max_interval is None or inter_arrival > stats.max_interval:
                stats.max_interval = inter_arrival
        
        for callback in self._callbacks:
            try:
                callback(observed)
            except Exception:
                pass
    
    def get_frames_by_id(self, arbitration_id: int) -> list[ObservedFrame]:
        """Get all buffered frames for a specific ID."""
        return [f for f in self._buffer if f.frame.arbitration_id == arbitration_id]
    
    def get_frames_in_window(
        self,
        start_time: float,
        end_time: float,
    ) -> list[ObservedFrame]:
        """Get frames within a time window."""
        return [
            f for f in self._buffer
            if start_time <= f.observation_time <= end_time
        ]
    
    def clear(self) -> None:
        """Clear the buffer and reset statistics."""
        self._buffer.clear()
        self._sequence = 0
        self._last_times.clear()
        self._statistics.clear()
        self._start_time = time.time()
    
    def summary(self) -> dict[str, object]:
        """Generate a summary of observations."""
        return {
            "total_frames": self._sequence,
            "unique_ids": len(self._statistics),
            "buffer_size": len(self._buffer),
            "observation_duration": (
                time.time() - self._start_time if self._start_time else 0
            ),
            "ids": list(self._statistics.keys()),
        }
