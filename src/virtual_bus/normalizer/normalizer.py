"""Frame normalization implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from virtual_bus.core.frame import CANFrame
from virtual_bus.normalizer.schema import MessageSchema, SignalSchema


@dataclass
class NormalizedSignal:
    """A decoded signal with its physical value and metadata."""
    
    name: str
    raw_value: int
    physical_value: float
    unit: str
    timestamp: float
    arbitration_id: int
    
    def __repr__(self) -> str:
        return f"{self.name}={self.physical_value:.3f}{self.unit}"


@dataclass
class NormalizedMessage:
    """A fully decoded CAN message with all signals."""
    
    arbitration_id: int
    name: str
    timestamp: float
    signals: dict[str, NormalizedSignal] = field(default_factory=dict)
    raw_data: bytes = field(default_factory=bytes)
    
    def get(self, signal_name: str) -> Optional[NormalizedSignal]:
        """Get a signal by name."""
        return self.signals.get(signal_name)
    
    def __repr__(self) -> str:
        sig_str = ", ".join(str(s) for s in self.signals.values())
        return f"{self.name}[{self.arbitration_id:#x}]: {sig_str}"


class FrameNormalizer:
    """Transforms raw CAN frames into normalized, semantic representations.
    
    The normalizer uses message schemas to decode raw bytes into physical
    values with units, enabling higher-level analysis and visualization.
    """
    
    def __init__(self) -> None:
        self._schemas: dict[int, MessageSchema] = {}
        self._unknown_ids: set[int] = set()
    
    @property
    def registered_ids(self) -> set[int]:
        """Set of arbitration IDs with registered schemas."""
        return set(self._schemas.keys())
    
    @property
    def unknown_ids(self) -> set[int]:
        """Set of arbitration IDs seen without schemas."""
        return self._unknown_ids.copy()
    
    def register_schema(self, schema: MessageSchema) -> None:
        """Register a message schema for decoding."""
        self._schemas[schema.arbitration_id] = schema
    
    def unregister_schema(self, arbitration_id: int) -> None:
        """Remove a registered schema."""
        self._schemas.pop(arbitration_id, None)
    
    def get_schema(self, arbitration_id: int) -> Optional[MessageSchema]:
        """Get the schema for an arbitration ID."""
        return self._schemas.get(arbitration_id)
    
    def normalize(self, frame: CANFrame) -> Optional[NormalizedMessage]:
        """Normalize a CAN frame using registered schemas.
        
        Returns None if no schema is registered for the frame's ID.
        """
        schema = self._schemas.get(frame.arbitration_id)
        
        if schema is None:
            self._unknown_ids.add(frame.arbitration_id)
            return None
        
        signals: dict[str, NormalizedSignal] = {}
        
        for signal_schema in schema.signals:
            try:
                physical_value = signal_schema.decode(frame.data)
                raw_value = self._extract_raw(frame.data, signal_schema)
                
                signals[signal_schema.name] = NormalizedSignal(
                    name=signal_schema.name,
                    raw_value=raw_value,
                    physical_value=physical_value,
                    unit=signal_schema.unit,
                    timestamp=frame.timestamp,
                    arbitration_id=frame.arbitration_id,
                )
            except Exception:
                continue
        
        return NormalizedMessage(
            arbitration_id=frame.arbitration_id,
            name=schema.name,
            timestamp=frame.timestamp,
            signals=signals,
            raw_data=frame.data,
        )
    
    def _extract_raw(self, data: bytes, signal: SignalSchema) -> int:
        """Extract raw integer value from data."""
        if len(data) == 0:
            return 0
        
        value = int.from_bytes(data, byteorder=signal.byte_order.value)
        mask = (1 << signal.bit_length) - 1
        return (value >> signal.start_bit) & mask
    
    def normalize_batch(
        self,
        frames: list[CANFrame],
    ) -> list[NormalizedMessage]:
        """Normalize multiple frames, skipping unknown IDs."""
        results = []
        for frame in frames:
            normalized = self.normalize(frame)
            if normalized is not None:
                results.append(normalized)
        return results
    
    def clear_unknown(self) -> None:
        """Clear the set of unknown IDs."""
        self._unknown_ids.clear()
