from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Union, Literal


# -----------------------------
# Constants (Classic CAN)
# -----------------------------
CAN_STD_ID_MAX = 0x7FF          # 11-bit
CAN_EXT_ID_MAX = 0x1FFFFFFF     # 29-bit
CAN_CLASSIC_MAX_DLC = 8


# -----------------------------
# Helpers
# -----------------------------
def _bytes_to_hex(data: bytes) -> str:
    return data.hex()

def _hex_to_bytes(hex_str: str) -> bytes:
    # Allow optional "0x" prefix and whitespace
    s = hex_str.strip().lower()
    if s.startswith("0x"):
        s = s[2:]
    if len(s) % 2 != 0:
        raise ValueError(f"Hex string must have even length, got {len(s)}")
    return bytes.fromhex(s)


# -----------------------------
# Core Data Types
# -----------------------------
@dataclass(frozen=True, slots=True)
class Frame:

    # Transport-level representation of a Classic CAN frame.
    # Notes:
    #  - CAN does not include a sender field; "source_node" is simulation-only
    #  - "timestamp_ns" should reflect observation time for timing analysis and replay

    timestamp_ns: int
    can_id: int
    data: bytes
    channel: str = "can0"
    is_extended_id: bool = False
    dlc: Optional[int] = None
    source_node: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.timestamp_ns < 0:
            raise ValueError("timestamp_ns must be non-negative")

        if self.is_extended_id:
            if not (0 <= self.can_id <= CAN_EXT_ID_MAX):
                raise ValueError(f"Extended CAN ID out of range: {self.can_id:#x}")
        else:
            if not (0 <= self.can_id <= CAN_STD_ID_MAX):
                raise ValueError(f"Standard CAN ID out of range: {self.can_id:#x}")

        if len(self.data) > CAN_CLASSIC_MAX_DLC:
            raise ValueError(
                f"Classic CAN data must be <= {CAN_CLASSIC_MAX_DLC} bytes; got {len(self.data)}"
            )

        inferred = len(self.data)
        if self.dlc is None:
            object.__setattr__(self, "dlc", inferred)
        else:
            if not (0 <= self.dlc <= CAN_CLASSIC_MAX_DLC):
                raise ValueError(f"dlc out of range for Classic CAN: {self.dlc}")
            # Enforce DLC == data length to keep things simple
            if self.dlc != inferred:
                raise ValueError(f"dlc ({self.dlc}) does not match data length ({inferred})")

    def to_dict(self) -> Dict[str, Any]:
        # JSONL-friendly serialization (bytes -> hex)
        return {
            "timestamp_ns": self.timestamp_ns,
            "can_id": self.can_id,
            "is_extended_id": self.is_extended_id,
            "dlc": self.dlc,
            "data_hex": _bytes_to_hex(self.data),
            "channel": self.channel,
            "source_node": self.source_node,
            "meta": self.meta,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Frame":
        # Inverse of to_dict().
        return Frame(
            timestamp_ns=int(d["timestamp_ns"]),
            can_id=int(d["can_id"]),
            data=_hex_to_bytes(d["data_hex"]),
            channel=str(d.get("channel", "can0")),
            is_extended_id=bool(d.get("is_extended_id", False)),
            dlc=int(d["dlc"]) if d.get("dlc") is not None else None,
            source_node=d.get("source_node"),
            meta=dict(d.get("meta", {})),
        )


SignalValue = Union[int, float, bool, str]


@dataclass(frozen=True, slots=True)
class Signal:

    # Semantic-level representation derived from Frames.
    # Signals are the canonical inputs to offline training and online scoring.

    timestamp_ns: int
    name: str
    value: SignalValue
    units: Optional[str] = None

    # Traceability back to transport-level origin
    source_can_id: Optional[int] = None
    source_channel: Optional[str] = None
    source_node: Optional[str] = None

    quality: Literal["OK", "UNMAPPED", "DECODE_ERROR"] = "OK"
    meta: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.timestamp_ns < 0:
            raise ValueError("timestamp_ns must be non-negative")
        if not self.name:
            raise ValueError("name must be a non-empty string")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp_ns": self.timestamp_ns,
            "name": self.name,
            "value": self.value,
            "units": self.units,
            "source_can_id": self.source_can_id,
            "source_channel": self.source_channel,
            "source_node": self.source_node,
            "quality": self.quality,
            "meta": self.meta,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Signal":
        return Signal(
            timestamp_ns=int(d["timestamp_ns"]),
            name=str(d["name"]),
            value=d["value"],
            units=d.get("units"),
            source_can_id=d.get("source_can_id"),
            source_channel=d.get("source_channel"),
            source_node=d.get("source_node"),
            quality=d.get("quality", "OK"),
            meta=dict(d.get("meta", {})),
        )


@dataclass(frozen=True, slots=True)
class Event:

    # Output of analysis/scoring, suitable for jsonl storage and dashboard display.

    timestamp_ns: int
    event_type: str
    severity: Literal["INFO", "WARN", "ERROR"] = "INFO"
    subject: Optional[str] = None  # e.g., signal name or can_id as string
    details: Dict[str, Any] = field(default_factory=dict)
    run_id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.timestamp_ns < 0:
            raise ValueError("timestamp_ns must be non-negative")
        if not self.event_type:
            raise ValueError("event_type must be non-empty")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp_ns": self.timestamp_ns,
            "event_type": self.event_type,
            "severity": self.severity,
            "subject": self.subject,
            "details": self.details,
            "run_id": self.run_id,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Event":
        return Event(
            timestamp_ns=int(d["timestamp_ns"]),
            event_type=str(d["event_type"]),
            severity=d.get("severity", "INFO"),
            subject=d.get("subject"),
            details=dict(d.get("details", {})),
            run_id=d.get("run_id"),
        )
