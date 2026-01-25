from __future__ import annotations

from pathlib import Path
from typing import Optional

from .types import Event, Signal
from .jsonl import JsonlWriter


class Analyzer:
    # Minimal rule-based analyzer:
    # - Detects if an 8-bit counter jumps by more than +1 (mod 256).
    
    def __init__(self, artifacts_dir: Path, watch_signal: str = "counter") -> None:
        self.watch_signal = watch_signal
        self.writer = JsonlWriter(artifacts_dir / "events.jsonl")
        self._last: Optional[int] = None
        self.count = 0

    def on_signal(self, sig: Signal) -> None:
        if sig.name != self.watch_signal or sig.quality != "OK":
            return
        v = int(sig.value)

        if self._last is not None:
            expected = (self._last + 1) % 256
            if v != expected:
                ev = Event(
                    timestamp_ns=sig.timestamp_ns,
                    event_type="COUNTER_JUMP",
                    severity="WARN",
                    subject=sig.name,
                    details={"last": self._last, "expected": expected, "got": v},
                )
                self.writer.append(ev.to_dict())
                self.count += 1

        self._last = v
