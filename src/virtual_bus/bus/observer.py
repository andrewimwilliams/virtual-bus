from __future__ import annotations

from pathlib import Path
from typing import Optional

from .types import Frame
from .jsonl import JsonlWriter


class Observer:
    # Passive capture: subscribes to the bus and records every frame unchanged.
    
    def __init__(self, artifacts_dir: Path, frames_filename: str = "frames.jsonl") -> None:
        self.writer = JsonlWriter(artifacts_dir / frames_filename)
        self.count = 0

    def on_frame(self, frame: Frame) -> None:
        self.writer.append(frame.to_dict())
        self.count += 1

    def close(self) -> None:
        self.writer.close()