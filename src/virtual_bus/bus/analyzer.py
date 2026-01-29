from __future__ import annotations

from pathlib import Path
from typing import Optional, Dict

from .types import Event, Signal
from .jsonl import JsonlWriter


class Analyzer:
    # Minimal rule-based analyzer:
    # - Detects if an 8-bit counter jumps by more than +1 (mod 256).
    
    def __init__(self, artifacts_dir: Path, watch_signals: Optional[set[str]] = None) -> None:
        # If None, analyze all signals
        self.watch_signals = watch_signals
        self.writer = JsonlWriter(artifacts_dir / "events.jsonl")
        self._last_by_name: Dict[str, int] = {}
        self.count = 0

    def on_signal(self, sig: Signal) -> None:
        if sig.quality != "OK":
            return
        if self.watch_signals is not None and sig.name not in self.watch_signals:
            return
        
        v = int(sig.value)
        last = self._last_by_name.get(sig.name)

        # ---- Rule 1: Counter jump ----
        if sig.name == "counter":
            if last is not None:
                expected = (last + 1) % 256
                if v != expected:
                    ev = Event(
                        timestamp_ns=sig.timestamp_ns,
                        event_type="COUNTER_JUMP",
                        severity="WARN",
                        subject=sig.name,
                        details={"last": last, "expected": expected, "got": v},
                    )
                    self.writer.append(ev.to_dict())
                    self.count += 1

            self._last_by_name[sig.name] = v
            return
        
        # ---- Rule 2: Temperature spike ----
        if sig.name == "temperature_deciC":
            if last is not None:
                dv = v - last
                if abs(dv) > 5:  # > 0.5C jump frame-to-frame
                    ev = Event(
                        timestamp_ns=sig.timestamp_ns,
                        event_type="TEMP_SPIKE",
                        severity="WARN",
                        subject=sig.name,
                        details={"last": last, "got": v, "delta_deciC": dv},
                    )
                    self.writer.append(ev.to_dict())
                    self.count += 1
            self._last_by_name[sig.name] = v
            return
        
        # ---- Rule 3: Voltage spike/sag ----
        if sig.name == "voltage_mv":
            if last is not None:
                dv = v - last
                if abs(dv) > 100:  # > 0.1V jump frame-to-frame
                    ev = Event(
                        timestamp_ns=sig.timestamp_ns,
                        event_type="VOLTAGE_SPIKE",
                        severity="WARN",
                        subject=sig.name,
                        details={"last": last, "got": v, "delta_mv": dv},
                    )
                    self.writer.append(ev.to_dict())
                    self.count += 1
            self._last_by_name[sig.name] = v
            return
        
        # Default: track last so future rules can be added easily
        self._last_by_name[sig.name] = v

    def close(self) -> None:
        self.writer.close()