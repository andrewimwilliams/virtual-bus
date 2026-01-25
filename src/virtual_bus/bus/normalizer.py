from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

from .types import Frame, Signal
from .jsonl import JsonlWriter


class Normalizer:
    # Minimal "frame -> signals" mapping.
    # mapping: can_id -> list of (signal_name, byte_index, units)

    def __init__(self, artifacts_dir: Path, mapping: Dict[int, List[Tuple[str, int, str]]]) -> None:
        self.mapping = mapping
        self.writer = JsonlWriter(artifacts_dir / "signals.jsonl")
        self.count = 0

    def on_frame(self, frame: Frame) -> None:
        specs = self.mapping.get(frame.can_id)
        if not specs:
            # still emit an "unmapped" signal so pipeline stays visible
            sig = Signal(
                timestamp_ns=frame.timestamp_ns,
                name="UNMAPPED",
                value=0,
                units=None,
                source_can_id=frame.can_id,
                source_channel=frame.channel,
                source_node=frame.source_node,
                quality="UNMAPPED",
            )
            self.writer.append(sig.to_dict())
            self.count += 1
            return

        for name, idx, units in specs:
            if idx >= len(frame.data):
                sig = Signal(
                    timestamp_ns=frame.timestamp_ns,
                    name=name,
                    value=0,
                    units=units,
                    source_can_id=frame.can_id,
                    source_channel=frame.channel,
                    source_node=frame.source_node,
                    quality="DECODE_ERROR",
                    meta={"reason": "byte_index_out_of_range", "idx": idx, "len": len(frame.data)},
                )
            else:
                sig = Signal(
                    timestamp_ns=frame.timestamp_ns,
                    name=name,
                    value=int(frame.data[idx]),
                    units=units,
                    source_can_id=frame.can_id,
                    source_channel=frame.channel,
                    source_node=frame.source_node,
                )

            self.writer.append(sig.to_dict())
            self.count += 1
