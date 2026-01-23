"""Traffic recording implementation."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, TextIO

from virtual_bus.core.frame import CANFrame
from virtual_bus.observer.observer import BusObserver, ObservedFrame


@dataclass
class RecordedFrame:
    """A frame with recording metadata."""
    
    arbitration_id: int
    data_hex: str
    timestamp: float
    relative_time: float
    is_extended_id: bool = False
    dlc: int = 0
    
    def to_can_frame(self) -> CANFrame:
        """Convert back to a CANFrame."""
        return CANFrame(
            arbitration_id=self.arbitration_id,
            data=bytes.fromhex(self.data_hex),
            timestamp=self.timestamp,
            is_extended_id=self.is_extended_id,
            dlc=self.dlc,
        )
    
    @classmethod
    def from_can_frame(cls, frame: CANFrame, start_time: float) -> RecordedFrame:
        """Create from a CANFrame."""
        return cls(
            arbitration_id=frame.arbitration_id,
            data_hex=frame.data.hex(),
            timestamp=frame.timestamp,
            relative_time=frame.timestamp - start_time,
            is_extended_id=frame.is_extended_id,
            dlc=frame.effective_dlc,
        )


@dataclass
class RecordingMetadata:
    """Metadata about a recording session."""
    
    start_time: float
    end_time: Optional[float] = None
    frame_count: int = 0
    unique_ids: list[int] = field(default_factory=list)
    description: str = ""
    
    @property
    def duration(self) -> Optional[float]:
        """Recording duration in seconds."""
        if self.end_time is None:
            return None
        return self.end_time - self.start_time


class TrafficRecorder:
    """Records CAN traffic with timing information for later replay.
    
    Recordings are stored in a JSON-based format that preserves
    timing characteristics for deterministic replay.
    """
    
    def __init__(self, observer: Optional[BusObserver] = None) -> None:
        self._observer = observer
        self._frames: list[RecordedFrame] = []
        self._metadata = RecordingMetadata(start_time=0)
        self._is_recording = False
        self._file: Optional[TextIO] = None
        self._stream_path: Optional[Path] = None
    
    @property
    def is_recording(self) -> bool:
        """Check if recording is active."""
        return self._is_recording
    
    @property
    def frame_count(self) -> int:
        """Number of recorded frames."""
        return len(self._frames)
    
    @property
    def metadata(self) -> RecordingMetadata:
        """Recording metadata."""
        return self._metadata
    
    def start(self, description: str = "") -> None:
        """Start recording."""
        if self._is_recording:
            return
        
        self._frames.clear()
        self._metadata = RecordingMetadata(
            start_time=time.time(),
            description=description,
        )
        self._is_recording = True
        
        if self._observer:
            self._observer.add_callback(self._on_frame)
    
    def stop(self) -> RecordingMetadata:
        """Stop recording and return metadata."""
        if not self._is_recording:
            return self._metadata
        
        self._is_recording = False
        self._metadata.end_time = time.time()
        self._metadata.frame_count = len(self._frames)
        self._metadata.unique_ids = list(set(f.arbitration_id for f in self._frames))
        
        if self._observer:
            self._observer.remove_callback(self._on_frame)
        
        if self._file:
            self._file.close()
            self._file = None
        
        return self._metadata
    
    def _on_frame(self, observed: ObservedFrame) -> None:
        """Handle an observed frame."""
        if not self._is_recording:
            return
        
        recorded = RecordedFrame.from_can_frame(
            observed.frame,
            self._metadata.start_time,
        )
        self._frames.append(recorded)
        
        if self._file:
            self._file.write(json.dumps(asdict(recorded)) + "\n")
            self._file.flush()
    
    def record_frame(self, frame: CANFrame) -> None:
        """Manually record a frame (for non-observer usage)."""
        if not self._is_recording:
            return
        
        recorded = RecordedFrame.from_can_frame(frame, self._metadata.start_time)
        self._frames.append(recorded)
    
    def save(self, path: Path | str) -> None:
        """Save the recording to a file."""
        path = Path(path)
        
        data = {
            "metadata": asdict(self._metadata),
            "frames": [asdict(f) for f in self._frames],
        }
        
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    
    def start_streaming(self, path: Path | str) -> None:
        """Start streaming recording directly to a file."""
        self._stream_path = Path(path)
        self._file = open(self._stream_path, "w")
        self.start()
    
    def get_frames(self) -> list[RecordedFrame]:
        """Get all recorded frames."""
        return self._frames.copy()
    
    def clear(self) -> None:
        """Clear recorded frames."""
        self._frames.clear()
        self._metadata = RecordingMetadata(start_time=0)


def load_recording(path: Path | str) -> tuple[RecordingMetadata, list[RecordedFrame]]:
    """Load a recording from a file."""
    path = Path(path)
    
    with open(path) as f:
        data = json.load(f)
    
    metadata = RecordingMetadata(**data["metadata"])
    frames = [RecordedFrame(**f) for f in data["frames"]]
    
    return metadata, frames
