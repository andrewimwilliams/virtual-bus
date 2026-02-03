from __future__ import annotations

from pathlib import Path
from typing import Optional, Dict

from .types import Event, Signal, FeedRecord
from .jsonl import JsonlWriter


class Analyzer:
    
    def __init__(self, artifacts_dir: Path, watch_signals: Optional[set[str]] = None) -> None:
        self.watch_signals = watch_signals
        self.feed_writer = JsonlWriter(artifacts_dir / "feed.jsonl")
        self.writer = JsonlWriter(artifacts_dir / "events.jsonl")
        self._last_by_name: Dict[str, int] = {}
        self.count = 0
        self.feed_count = 0

    def on_signal(self, sig: Signal) -> None:
        rec = FeedRecord(
            timestamp_ns=sig.timestamp_ns,
            record_type="SIGNAL",
            severity="INFO" if sig.quality == "OK" else "WARN",
            subject=sig.name,
            details={
                "value": sig.value,
                "units": sig.units,
                "quality": sig.quality,
                "source_can_id": sig.source_can_id,
                "source_channel": sig.source_channel,
                "source_node": sig.source_node,
                "meta": sig.meta,
            },
        )

        self.feed_writer.append(rec.to_dict())

        self.feed_count += 1

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
                        details={
                            "last": last,
                            "expected": expected,
                            "got": v,
                            "units": sig.units,
                            "source_can_id": sig.source_can_id,
                            "source_node": sig.source_node,
                        },
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
                        details={
                            "last": last,
                            "got": v,
                            "delta_deciC": dv,
                            "units": sig.units,
                            "source_can_id": sig.source_can_id,
                            "source_node": sig.source_node,
                        },
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
                        details={
                            "last": last,
                            "got": v,
                            "delta_mv": dv,
                            "units": sig.units,
                            "source_can_id": sig.source_can_id,
                            "source_node": sig.source_node,
                        },
                    )
                    self.writer.append(ev.to_dict())
                    self.count += 1
            self._last_by_name[sig.name] = v
            return
        
        # Default: track last so future rules can be added easily
        self._last_by_name[sig.name] = v

    def close(self) -> None:
        self.writer.close()
        self.feed_writer.close()