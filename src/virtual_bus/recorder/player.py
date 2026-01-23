"""Traffic replay implementation."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from virtual_bus.core.frame import CANFrame
from virtual_bus.core.bus import VirtualCANBus
from virtual_bus.recorder.recorder import RecordedFrame, RecordingMetadata, load_recording


class PlaybackState(Enum):
    """Playback state."""
    
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"


@dataclass
class PlaybackProgress:
    """Current playback progress."""
    
    current_frame: int
    total_frames: int
    elapsed_time: float
    total_duration: float
    state: PlaybackState
    
    @property
    def progress_percent(self) -> float:
        """Progress as percentage."""
        if self.total_frames == 0:
            return 0.0
        return (self.current_frame / self.total_frames) * 100


class TrafficPlayer:
    """Replays recorded CAN traffic with deterministic timing.
    
    The player can replay traffic at original speed, scaled speed,
    or as fast as possible for analysis purposes.
    """
    
    def __init__(
        self,
        bus: Optional[VirtualCANBus] = None,
        speed_factor: float = 1.0,
    ) -> None:
        self._bus = bus
        self._speed_factor = speed_factor
        self._frames: list[RecordedFrame] = []
        self._metadata: Optional[RecordingMetadata] = None
        self._state = PlaybackState.STOPPED
        self._current_index = 0
        self._start_time: Optional[float] = None
        self._pause_time: Optional[float] = None
        self._task: Optional[asyncio.Task[None]] = None
        self._callbacks: list[Callable[[CANFrame, int], None]] = []
    
    @property
    def state(self) -> PlaybackState:
        """Current playback state."""
        return self._state
    
    @property
    def speed_factor(self) -> float:
        """Playback speed factor (1.0 = real-time)."""
        return self._speed_factor
    
    @speed_factor.setter
    def speed_factor(self, value: float) -> None:
        """Set playback speed factor."""
        if value <= 0:
            raise ValueError("Speed factor must be positive")
        self._speed_factor = value
    
    @property
    def progress(self) -> PlaybackProgress:
        """Get current playback progress."""
        elapsed = 0.0
        if self._start_time:
            if self._pause_time:
                elapsed = self._pause_time - self._start_time
            else:
                elapsed = time.time() - self._start_time
        
        total_duration = 0.0
        if self._metadata and self._metadata.duration:
            total_duration = self._metadata.duration
        
        return PlaybackProgress(
            current_frame=self._current_index,
            total_frames=len(self._frames),
            elapsed_time=elapsed,
            total_duration=total_duration,
            state=self._state,
        )
    
    def load(self, path: Path | str) -> RecordingMetadata:
        """Load a recording from file."""
        self._metadata, self._frames = load_recording(path)
        self._current_index = 0
        return self._metadata
    
    def load_frames(
        self,
        frames: list[RecordedFrame],
        metadata: Optional[RecordingMetadata] = None,
    ) -> None:
        """Load frames directly."""
        self._frames = frames.copy()
        self._metadata = metadata
        self._current_index = 0
    
    def add_callback(self, callback: Callable[[CANFrame, int], None]) -> None:
        """Add callback for each replayed frame."""
        self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[CANFrame, int], None]) -> None:
        """Remove a callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    async def play(self) -> None:
        """Start or resume playback."""
        if self._state == PlaybackState.PLAYING:
            return
        
        if not self._frames:
            return
        
        if self._state == PlaybackState.PAUSED and self._pause_time and self._start_time:
            pause_duration = time.time() - self._pause_time
            self._start_time += pause_duration
            self._pause_time = None
        else:
            self._start_time = time.time()
            self._current_index = 0
        
        self._state = PlaybackState.PLAYING
        self._task = asyncio.create_task(self._playback_loop())
    
    async def pause(self) -> None:
        """Pause playback."""
        if self._state != PlaybackState.PLAYING:
            return
        
        self._state = PlaybackState.PAUSED
        self._pause_time = time.time()
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def stop(self) -> None:
        """Stop playback."""
        self._state = PlaybackState.STOPPED
        self._current_index = 0
        self._start_time = None
        self._pause_time = None
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
    
    def seek(self, frame_index: int) -> None:
        """Seek to a specific frame index."""
        if 0 <= frame_index < len(self._frames):
            self._current_index = frame_index
    
    async def _playback_loop(self) -> None:
        """Main playback loop."""
        if not self._start_time:
            return
        
        while self._state == PlaybackState.PLAYING and self._current_index < len(self._frames):
            recorded = self._frames[self._current_index]
            
            target_time = self._start_time + (recorded.relative_time / self._speed_factor)
            now = time.time()
            
            if target_time > now:
                await asyncio.sleep(target_time - now)
            
            if self._state != PlaybackState.PLAYING:
                break
            
            frame = recorded.to_can_frame()
            frame = CANFrame(
                arbitration_id=frame.arbitration_id,
                data=frame.data,
                timestamp=time.time(),
                is_extended_id=frame.is_extended_id,
                dlc=frame.dlc,
            )
            
            if self._bus:
                await self._bus.transmit(frame)
            
            for callback in self._callbacks:
                try:
                    callback(frame, self._current_index)
                except Exception:
                    pass
            
            self._current_index += 1
        
        if self._current_index >= len(self._frames):
            self._state = PlaybackState.STOPPED
    
    async def play_instant(self) -> int:
        """Play all frames as fast as possible (no timing). Returns frame count."""
        count = 0
        for i, recorded in enumerate(self._frames):
            frame = recorded.to_can_frame()
            
            if self._bus:
                await self._bus.transmit(frame)
            
            for callback in self._callbacks:
                try:
                    callback(frame, i)
                except Exception:
                    pass
            
            count += 1
        
        return count
