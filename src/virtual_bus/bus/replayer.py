from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Optional
import json
import time

from .types import Frame


@dataclass
class FrameReplayer:
    # Replays previously recorded frames from a JSONL file.

    # timing:
    #  - "none": publish as fast as possible
    #  - "relative": sleep based on deltas of recorded timestamp_ns

    # speed:
    #  - 1.0 = real-time (for timing="relative")
    #  - 10.0 = 10x faster replay
    
    path: Path
    timing: str = "none"      # "none" | "relative"
    speed: float = 1.0
    max_sleep_s: float = 0.25 # cap sleeps to keep replay responsive

    def _iter_frames(self) -> Iterator[Frame]:
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                yield Frame.from_dict(d)

    def run(self, publish: Callable[[Frame], None], limit: Optional[int] = None) -> int:
        if self.speed <= 0:
            raise ValueError("speed must be > 0")

        count = 0
        prev_ts: Optional[int] = None

        for frame in self._iter_frames():
            if limit is not None and count >= limit:
                break

            if self.timing == "relative" and prev_ts is not None:
                dt_ns = frame.timestamp_ns - prev_ts
                if dt_ns > 0:
                    sleep_s = (dt_ns / 1e9) / self.speed
                    if sleep_s > 0:
                        time.sleep(min(sleep_s, self.max_sleep_s))

            publish(frame)
            prev_ts = frame.timestamp_ns
            count += 1

        return count
