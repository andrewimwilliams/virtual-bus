"""CAN node implementation."""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional, TYPE_CHECKING

from virtual_bus.core.frame import CANFrame

if TYPE_CHECKING:
    from virtual_bus.core.bus import VirtualCANBus


class TransmitMode(Enum):
    """Transmission scheduling mode."""
    
    PERIODIC = "periodic"
    ON_CHANGE = "on_change"
    ON_DEMAND = "on_demand"


@dataclass
class MessageConfig:
    """Configuration for a periodic message."""
    
    arbitration_id: int
    period_ms: float
    data_generator: Callable[[], bytes]
    is_extended_id: bool = False
    jitter_ms: float = 0.0
    enabled: bool = True


@dataclass
class FaultConfig:
    """Configuration for fault injection."""
    
    drop_probability: float = 0.0
    delay_ms: float = 0.0
    delay_jitter_ms: float = 0.0
    corrupt_probability: float = 0.0


class CANNode:
    """A virtual CAN node that can transmit and receive frames.
    
    Nodes can be configured to:
    - Transmit periodic messages with configurable timing
    - Receive and filter incoming frames
    - Inject faults for testing
    """
    
    def __init__(
        self,
        name: str,
        node_id: int = 0,
        fault_config: Optional[FaultConfig] = None,
    ) -> None:
        self.name = name
        self.node_id = node_id
        self._bus: Optional[VirtualCANBus] = None
        self._messages: list[MessageConfig] = []
        self._receive_callbacks: list[Callable[[CANFrame], None]] = []
        self._filter_ids: Optional[set[int]] = None
        self._running = False
        self._tasks: list[asyncio.Task[None]] = []
        self._fault_config = fault_config or FaultConfig()
        self._frames_sent = 0
        self._frames_received = 0
        self._frames_dropped = 0
    
    @property
    def is_connected(self) -> bool:
        """Check if node is connected to a bus."""
        return self._bus is not None
    
    @property
    def statistics(self) -> dict[str, int]:
        """Return node statistics."""
        return {
            "frames_sent": self._frames_sent,
            "frames_received": self._frames_received,
            "frames_dropped": self._frames_dropped,
        }
    
    def add_periodic_message(self, config: MessageConfig) -> None:
        """Add a periodic message to transmit."""
        self._messages.append(config)
    
    def add_receive_callback(self, callback: Callable[[CANFrame], None]) -> None:
        """Add a callback for received frames."""
        self._receive_callbacks.append(callback)
    
    def set_filter(self, arbitration_ids: Optional[set[int]]) -> None:
        """Set receive filter. None means accept all."""
        self._filter_ids = arbitration_ids
    
    async def transmit(self, frame: CANFrame) -> bool:
        """Transmit a frame on the bus."""
        if not self._bus:
            return False
        
        if random.random() < self._fault_config.drop_probability:
            self._frames_dropped += 1
            return False
        
        if self._fault_config.delay_ms > 0:
            delay = self._fault_config.delay_ms
            if self._fault_config.delay_jitter_ms > 0:
                delay += random.uniform(
                    -self._fault_config.delay_jitter_ms,
                    self._fault_config.delay_jitter_ms
                )
            await asyncio.sleep(max(0, delay) / 1000.0)
        
        await self._bus.transmit(frame)
        self._frames_sent += 1
        return True
    
    async def receive(self, frame: CANFrame) -> None:
        """Called by the bus when a frame is received."""
        if self._filter_ids is not None and frame.arbitration_id not in self._filter_ids:
            return
        
        self._frames_received += 1
        
        for callback in self._receive_callbacks:
            try:
                callback(frame)
            except Exception:
                pass
    
    async def _periodic_transmit(self, config: MessageConfig) -> None:
        """Transmit a message periodically."""
        while self._running and config.enabled:
            data = config.data_generator()
            frame = CANFrame(
                arbitration_id=config.arbitration_id,
                data=data,
                timestamp=time.time(),
                is_extended_id=config.is_extended_id,
            )
            await self.transmit(frame)
            
            period = config.period_ms
            if config.jitter_ms > 0:
                period += random.uniform(-config.jitter_ms, config.jitter_ms)
            
            await asyncio.sleep(max(1, period) / 1000.0)
    
    async def start(self) -> None:
        """Start the node's periodic transmissions."""
        if self._running:
            return
        
        self._running = True
        
        for msg_config in self._messages:
            if msg_config.enabled:
                task = asyncio.create_task(self._periodic_transmit(msg_config))
                self._tasks.append(task)
    
    async def stop(self) -> None:
        """Stop the node's periodic transmissions."""
        self._running = False
        
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._tasks.clear()
    
    async def __aenter__(self) -> CANNode:
        await self.start()
        return self
    
    async def __aexit__(self, *args: object) -> None:
        await self.stop()
