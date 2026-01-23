"""Tests for CAN frame implementation."""

import pytest
from virtual_bus.core.frame import CANFrame


class TestCANFrame:
    """Tests for CANFrame class."""
    
    def test_create_basic_frame(self) -> None:
        """Test creating a basic CAN frame."""
        frame = CANFrame(
            arbitration_id=0x100,
            data=bytes([0x01, 0x02, 0x03, 0x04]),
        )
        
        assert frame.arbitration_id == 0x100
        assert frame.data == bytes([0x01, 0x02, 0x03, 0x04])
        assert frame.effective_dlc == 4
        assert not frame.is_extended_id
        assert not frame.is_remote_frame
    
    def test_frame_hex_data(self) -> None:
        """Test hex data representation."""
        frame = CANFrame(
            arbitration_id=0x100,
            data=bytes([0xDE, 0xAD, 0xBE, 0xEF]),
        )
        
        assert frame.hex_data() == "DEADBEEF"
    
    def test_frame_empty_data(self) -> None:
        """Test frame with empty data."""
        frame = CANFrame(arbitration_id=0x100, data=bytes())
        
        assert frame.effective_dlc == 0
        assert frame.hex_data() == ""
    
    def test_frame_max_data(self) -> None:
        """Test frame with maximum 8 bytes."""
        data = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08])
        frame = CANFrame(arbitration_id=0x100, data=data)
        
        assert frame.effective_dlc == 8
        assert len(frame.data) == 8
    
    def test_frame_data_too_long(self) -> None:
        """Test that data longer than 8 bytes raises error."""
        with pytest.raises(ValueError, match="cannot exceed 8 bytes"):
            CANFrame(
                arbitration_id=0x100,
                data=bytes([0] * 9),
            )
    
    def test_standard_id_valid_range(self) -> None:
        """Test valid standard ID range (0-0x7FF)."""
        CANFrame(arbitration_id=0x000)
        CANFrame(arbitration_id=0x7FF)
    
    def test_standard_id_invalid(self) -> None:
        """Test invalid standard ID."""
        with pytest.raises(ValueError, match="Standard arbitration ID"):
            CANFrame(arbitration_id=0x800)
    
    def test_extended_id_valid_range(self) -> None:
        """Test valid extended ID range (0-0x1FFFFFFF)."""
        CANFrame(arbitration_id=0x000, is_extended_id=True)
        CANFrame(arbitration_id=0x1FFFFFFF, is_extended_id=True)
        CANFrame(arbitration_id=0x800, is_extended_id=True)
    
    def test_extended_id_invalid(self) -> None:
        """Test invalid extended ID."""
        with pytest.raises(ValueError, match="Extended arbitration ID"):
            CANFrame(arbitration_id=0x20000000, is_extended_id=True)
    
    def test_frame_immutable(self) -> None:
        """Test that frame is immutable (frozen dataclass)."""
        frame = CANFrame(arbitration_id=0x100, data=bytes([0x01]))
        
        with pytest.raises(AttributeError):
            frame.arbitration_id = 0x200  # type: ignore
    
    def test_frame_repr(self) -> None:
        """Test frame string representation."""
        frame = CANFrame(
            arbitration_id=0x100,
            data=bytes([0xAB, 0xCD]),
        )
        
        repr_str = repr(frame)
        assert "0x100" in repr_str
        assert "ABCD" in repr_str
    
    def test_frame_with_explicit_dlc(self) -> None:
        """Test frame with explicit DLC different from data length."""
        frame = CANFrame(
            arbitration_id=0x100,
            data=bytes([0x01, 0x02]),
            dlc=4,
        )
        
        assert frame.effective_dlc == 4
        assert len(frame.data) == 2
