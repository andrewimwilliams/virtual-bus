"""Signal schema definitions for frame normalization."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ByteOrder(Enum):
    """Byte ordering for multi-byte signals."""
    
    LITTLE_ENDIAN = "little"
    BIG_ENDIAN = "big"


class ValueType(Enum):
    """Signal value types."""
    
    UNSIGNED = "unsigned"
    SIGNED = "signed"
    FLOAT = "float"


@dataclass
class SignalSchema:
    """Schema definition for a single signal within a CAN message.
    
    Signals are extracted from the raw payload bytes using bit-level
    addressing. The start_bit is the LSB position in the payload.
    """
    
    name: str
    start_bit: int
    bit_length: int
    byte_order: ByteOrder = ByteOrder.LITTLE_ENDIAN
    value_type: ValueType = ValueType.UNSIGNED
    scale: float = 1.0
    offset: float = 0.0
    unit: str = ""
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    description: str = ""
    
    def decode(self, data: bytes) -> float:
        """Decode the signal value from raw bytes."""
        if len(data) == 0:
            return self.offset
        
        value = int.from_bytes(data, byteorder=self.byte_order.value)
        
        start_byte = self.start_bit // 8
        start_bit_in_byte = self.start_bit % 8
        
        mask = (1 << self.bit_length) - 1
        raw_value = (value >> self.start_bit) & mask
        
        if self.value_type == ValueType.SIGNED:
            sign_bit = 1 << (self.bit_length - 1)
            if raw_value & sign_bit:
                raw_value -= 1 << self.bit_length
        
        physical_value = raw_value * self.scale + self.offset
        
        return physical_value
    
    def encode(self, physical_value: float) -> int:
        """Encode a physical value to raw bits."""
        raw_value = int((physical_value - self.offset) / self.scale)
        
        if self.value_type == ValueType.SIGNED and raw_value < 0:
            raw_value += 1 << self.bit_length
        
        mask = (1 << self.bit_length) - 1
        return raw_value & mask


@dataclass
class MessageSchema:
    """Schema definition for a complete CAN message.
    
    A message schema maps an arbitration ID to a set of signal definitions,
    enabling automatic decoding of raw frames into semantic values.
    """
    
    arbitration_id: int
    name: str
    signals: list[SignalSchema] = field(default_factory=list)
    is_extended_id: bool = False
    dlc: int = 8
    cycle_time_ms: Optional[float] = None
    description: str = ""
    
    def add_signal(self, signal: SignalSchema) -> None:
        """Add a signal to the message schema."""
        self.signals.append(signal)
    
    def get_signal(self, name: str) -> Optional[SignalSchema]:
        """Get a signal by name."""
        for signal in self.signals:
            if signal.name == name:
                return signal
        return None
