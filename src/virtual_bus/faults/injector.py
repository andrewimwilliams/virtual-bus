"""Fault injection implementation."""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

from virtual_bus.core.frame import CANFrame
from virtual_bus.core.bus import VirtualCANBus


class FaultType(Enum):
    """Types of faults that can be injected."""
    
    DROP = "drop"
    DELAY = "delay"
    CORRUPT = "corrupt"
    DUPLICATE = "duplicate"
    BURST = "burst"
    REORDER = "reorder"


@dataclass
class FaultRule:
    """A rule for fault injection."""
    
    fault_type: FaultType
    probability: float = 0.1
    target_ids: Optional[set[int]] = None
    delay_ms: float = 0.0
    delay_jitter_ms: float = 0.0
    burst_count: int = 5
    burst_interval_ms: float = 1.0
    enabled: bool = True
    
    def applies_to(self, arbitration_id: int) -> bool:
        """Check if this rule applies to a given ID."""
        if self.target_ids is None:
            return True
        return arbitration_id in self.target_ids


@dataclass
class FaultStatistics:
    """Statistics about injected faults."""
    
    frames_processed: int = 0
    frames_dropped: int = 0
    frames_delayed: int = 0
    frames_corrupted: int = 0
    frames_duplicated: int = 0
    bursts_injected: int = 0


class FaultInjector:
    """Injects faults into CAN bus traffic for testing.
    
    The injector can be configured with rules that specify
    what types of faults to inject and under what conditions.
    """
    
    def __init__(self, bus: Optional[VirtualCANBus] = None) -> None:
        self._bus = bus
        self._rules: list[FaultRule] = []
        self._statistics = FaultStatistics()
        self._enabled = True
        self._pending_frames: list[tuple[float, CANFrame]] = []
    
    @property
    def statistics(self) -> FaultStatistics:
        """Get fault injection statistics."""
        return self._statistics
    
    @property
    def enabled(self) -> bool:
        """Check if fault injection is enabled."""
        return self._enabled
    
    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Enable or disable fault injection."""
        self._enabled = value
    
    def add_rule(self, rule: FaultRule) -> None:
        """Add a fault injection rule."""
        self._rules.append(rule)
    
    def remove_rule(self, rule: FaultRule) -> None:
        """Remove a fault injection rule."""
        if rule in self._rules:
            self._rules.remove(rule)
    
    def clear_rules(self) -> None:
        """Remove all rules."""
        self._rules.clear()
    
    async def process_frame(self, frame: CANFrame) -> list[CANFrame]:
        """Process a frame through fault injection rules.
        
        Returns a list of frames to transmit (may be empty, single, or multiple).
        """
        self._statistics.frames_processed += 1
        
        if not self._enabled:
            return [frame]
        
        result_frames: list[CANFrame] = [frame]
        
        for rule in self._rules:
            if not rule.enabled:
                continue
            
            if not rule.applies_to(frame.arbitration_id):
                continue
            
            if random.random() > rule.probability:
                continue
            
            if rule.fault_type == FaultType.DROP:
                self._statistics.frames_dropped += 1
                return []
            
            elif rule.fault_type == FaultType.DELAY:
                delay = rule.delay_ms
                if rule.delay_jitter_ms > 0:
                    delay += random.uniform(-rule.delay_jitter_ms, rule.delay_jitter_ms)
                await asyncio.sleep(max(0, delay) / 1000.0)
                self._statistics.frames_delayed += 1
            
            elif rule.fault_type == FaultType.CORRUPT:
                corrupted_data = self._corrupt_data(frame.data)
                result_frames = [CANFrame(
                    arbitration_id=frame.arbitration_id,
                    data=corrupted_data,
                    timestamp=frame.timestamp,
                    is_extended_id=frame.is_extended_id,
                )]
                self._statistics.frames_corrupted += 1
            
            elif rule.fault_type == FaultType.DUPLICATE:
                result_frames = [frame, frame]
                self._statistics.frames_duplicated += 1
            
            elif rule.fault_type == FaultType.BURST:
                burst_frames = []
                for i in range(rule.burst_count):
                    burst_frames.append(CANFrame(
                        arbitration_id=frame.arbitration_id,
                        data=frame.data,
                        timestamp=time.time(),
                        is_extended_id=frame.is_extended_id,
                    ))
                result_frames = burst_frames
                self._statistics.bursts_injected += 1
        
        return result_frames
    
    def _corrupt_data(self, data: bytes) -> bytes:
        """Corrupt data by flipping random bits."""
        if len(data) == 0:
            return data
        
        data_list = list(data)
        byte_idx = random.randint(0, len(data_list) - 1)
        bit_idx = random.randint(0, 7)
        data_list[byte_idx] ^= (1 << bit_idx)
        
        return bytes(data_list)
    
    async def inject_burst(
        self,
        arbitration_id: int,
        data: bytes,
        count: int = 10,
        interval_ms: float = 1.0,
    ) -> int:
        """Inject a burst of frames onto the bus."""
        if not self._bus:
            return 0
        
        for i in range(count):
            frame = CANFrame(
                arbitration_id=arbitration_id,
                data=data,
                timestamp=time.time(),
            )
            await self._bus.transmit(frame)
            
            if i < count - 1:
                await asyncio.sleep(interval_ms / 1000.0)
        
        self._statistics.bursts_injected += 1
        return count
    
    def reset_statistics(self) -> None:
        """Reset fault statistics."""
        self._statistics = FaultStatistics()
