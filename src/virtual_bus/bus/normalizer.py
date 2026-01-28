from __future__ import annotations

from pathlib import Path
from typing import Callable, Union

from .types import Frame, Signal
from .jsonl import JsonlWriter

# Old: (name, byte_index, units)
SignalSpecV1 = tuple[str, int, str | None]

# New: (name, dtype, offset, units)
# dtype: "u8" | "u16_le" for now
SignalSpecV2 = tuple[str, str, int, str | None]

SignalSpec = Union[SignalSpecV1, SignalSpecV2]
SignalMap = dict[int, list[SignalSpec]]


class Normalizer:
    # frame -> signals stage

    def __init__(
        self,
        artifacts_dir: Path,
        mapping: SignalMap,
        publish_signal: Callable[[Signal], None],
    ) -> None:
        self.mapping = mapping
        self.publish_signal = publish_signal
        self.writer = JsonlWriter(artifacts_dir / "signals.jsonl")
        self.count = 0

    def _emit(self, sig: Signal) -> None:
        self.writer.append(sig.to_dict())
        self.publish_signal(sig)
        self.count += 1

    def _decode(self, frame: Frame, *, dtype: str, offset: int) -> tuple[int | None, dict | None]:
        
        data = frame.data

        if dtype == "u8":
            if offset >= len(data):
                return None, {"reason": "byte_index_out_of_range", "idx": offset, "len": len(data)}
            return int(data[offset]), None

        if dtype == "u16_le":
            if offset + 1 >= len(data):
                return None, {"reason": "u16_le_out_of_range", "offset": offset, "len": len(data)}
            return int.from_bytes(data[offset : offset + 2], byteorder="little", signed=False), None

        return None, {"reason": "unknown_dtype", "dtype": dtype}

    def on_frame(self, frame: Frame) -> None:
        specs = self.mapping.get(frame.can_id)
        if not specs:
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
            self._emit(sig)
            return

        for spec in specs:
            # V1: (name, idx, units)
            if len(spec) == 3:
                name, idx, units = spec
                dtype = "u8"
                offset = idx
            # V2: (name, dtype, offset, units)
            elif len(spec) == 4:
                name, dtype, offset, units = spec
            else:
                sig = Signal(
                    timestamp_ns=frame.timestamp_ns,
                    name="DECODE_ERROR",
                    value=0,
                    units=None,
                    source_can_id=frame.can_id,
                    source_channel=frame.channel,
                    source_node=frame.source_node,
                    quality="DECODE_ERROR",
                    meta={"reason": "invalid_spec_tuple", "spec": repr(spec)},
                )
                self._emit(sig)
                continue

            value, err = self._decode(frame, dtype=dtype, offset=offset)
            if err is not None:
                sig = Signal(
                    timestamp_ns=frame.timestamp_ns,
                    name=name,
                    value=0,
                    units=units,
                    source_can_id=frame.can_id,
                    source_channel=frame.channel,
                    source_node=frame.source_node,
                    quality="DECODE_ERROR",
                    meta=err,
                )
            else:
                sig = Signal(
                    timestamp_ns=frame.timestamp_ns,
                    name=name,
                    value=value,
                    units=units,
                    source_can_id=frame.can_id,
                    source_channel=frame.channel,
                    source_node=frame.source_node,
                )
            self._emit(sig)

    def close(self) -> None:
        self.writer.close()
