"""Virtual CAN bus implementation."""

from __future__ import annotations

import asyncio
import time
from asyncio import QueueEmpty
from dataclasses import dataclass, field
from typing import Callable, Optional, TYPE_CHECKING

from virtual_bus.core.frame import CANFrame

if TYPE_CHECKING:
    from virtual_bus.core.node import CANNode


FrameCallback = Callable[[CANFrame], None]


@dataclass
class BusStatistics:
    """Statistics about bus activity."""
    
    frames_transmitted: int = 0
    bytes_transmitted: int = 0
    start_time: float = field(default_factory=time.time)
    last_frame_time: Optional[float] = None
    
    @property
    def elapsed_time(self) -> float:
        """Time since bus started."""
        return time.time() - self.start_time
    
    @property
    def frames_per_second(self) -> float:
        """Average frame rate."""
        elapsed = self.elapsed_time
        if elapsed <= 0:
            return 0.0
        return self.frames_transmitted / elapsed


class VirtualCANBus:
    """A virtual CAN bus that connects multiple nodes.
    
    The bus simulates message-based communication where frames are
    broadcast to all connected nodes. Priority is determined by
    arbitration ID (lower ID = higher priority).
    """
    
    def __init__(self, name: str = "vcan0") -> None:
        self.name = name
        self._nodes: list[CANNode] = []
        self._observers: list[FrameCallback] = []
        self._frame_queue: Optional[asyncio.Queue[CANFrame]] = None
        self._running = False
        self._task: Optional[asyncio.Task[None]] = None
        self._statistics = BusStatistics()
        self._lock: Optional[asyncio.Lock] = None
    
    @property
    def statistics(self) -> BusStatistics:
        """Return current bus statistics."""
        return self._statistics
    
    def attach_node(self, node: CANNode) -> None:
        """Attach a node to the bus."""
        if node not in self._nodes:
            self._nodes.append(node)
            node._bus = self
    
    def detach_node(self, node: CANNode) -> None:
        """Detach a node from the bus."""
        if node in self._nodes:
            self._nodes.remove(node)
            node._bus = None
    
    def add_observer(self, callback: FrameCallback) -> None:
        """Add an observer callback that receives all frames."""
        if callback not in self._observers:
            self._observers.append(callback)
    
    def remove_observer(self, callback: FrameCallback) -> None:
        """Remove an observer callback."""
        if callback in self._observers:
            self._observers.remove(callback)
    
    async def transmit(self, frame: CANFrame) -> None:
        """Queue a frame for transmission on the bus."""
        if self._frame_queue is not None:
            await self._frame_queue.put(frame)
    
    def transmit_sync(self, frame: CANFrame) -> None:
        """Synchronously queue a frame (for use in non-async contexts)."""
        if self._frame_queue is None:
            return
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(self._frame_queue.put_nowait, frame)
        except RuntimeError:
            self._frame_queue.put_nowait(frame)
    
    async def _process_frames(self) -> None:
        """Process frames from the queue and broadcast to nodes/observers."""
        if self._frame_queue is None or self._lock is None:
            return
        while self._running:
            try:
                frame = await asyncio.wait_for(self._frame_queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            
            async with self._lock:
                self._statistics.frames_transmitted += 1
                self._statistics.bytes_transmitted += len(frame.data)
                self._statistics.last_frame_time = frame.timestamp
                
                for node in self._nodes:
                    await node.receive(frame)
                
                for observer in self._observers:
                    try:
                        observer(frame)
                    except Exception:
                        pass
    
    async def start(self) -> None:
        """Start the bus processing loop."""
        if self._running:
            return
        
        self._running = True
        self._statistics = BusStatistics()
        self._frame_queue = asyncio.Queue()
        self._lock = asyncio.Lock()
        self._task = asyncio.create_task(self._process_frames())
    
    async def stop(self) -> None:
        """Stop the bus processing loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        
        # Drain the queue
        while not self._frame_queue.empty():
            try:
                self._frame_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
    
    async def __aenter__(self) -> VirtualCANBus:
        await self.start()
        return self
    
    async def __aexit__(self, *args: object) -> None:
        await self.stop()
