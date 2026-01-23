"""CAN frame representation."""

from dataclasses import dataclass, field
from typing import Optional
import time


@dataclass(frozen=True)
class CANFrame:
    """Represents a single CAN frame.
    
    Attributes:
        arbitration_id: 11-bit (standard) or 29-bit (extended) message identifier.
        data: Payload bytes (0-8 bytes for classical CAN).
        timestamp: Time when the frame was transmitted/received (seconds since epoch).
        is_extended_id: True if using 29-bit extended identifier.
        is_remote_frame: True if this is a remote transmission request (RTR).
        dlc: Data Length Code (0-8 for classical CAN).
    """
    
    arbitration_id: int
    data: bytes = field(default_factory=bytes)
    timestamp: float = field(default_factory=time.time)
    is_extended_id: bool = False
    is_remote_frame: bool = False
    dlc: Optional[int] = None
    
    def __post_init__(self) -> None:
        if len(self.data) > 8:
            raise ValueError(f"CAN frame data cannot exceed 8 bytes, got {len(self.data)}")
        
        if self.is_extended_id:
            if not (0 <= self.arbitration_id <= 0x1FFFFFFF):
                raise ValueError(
                    f"Extended arbitration ID must be 0-0x1FFFFFFF, got {self.arbitration_id:#x}"
                )
        else:
            if not (0 <= self.arbitration_id <= 0x7FF):
                raise ValueError(
                    f"Standard arbitration ID must be 0-0x7FF, got {self.arbitration_id:#x}"
                )
    
    @property
    def effective_dlc(self) -> int:
        """Return the effective DLC (data length code)."""
        if self.dlc is not None:
            return self.dlc
        return len(self.data)
    
    def hex_data(self) -> str:
        """Return data as a hex string."""
        return self.data.hex().upper()
    
    def __repr__(self) -> str:
        id_str = f"{self.arbitration_id:#05x}" if not self.is_extended_id else f"{self.arbitration_id:#010x}"
        return (
            f"CANFrame(id={id_str}, data={self.hex_data()}, "
            f"dlc={self.effective_dlc}, ts={self.timestamp:.6f})"
        )
