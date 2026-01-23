"""Tests for frame normalization."""

import pytest
from virtual_bus.core.frame import CANFrame
from virtual_bus.normalizer.normalizer import FrameNormalizer
from virtual_bus.normalizer.schema import (
    MessageSchema,
    SignalSchema,
    ByteOrder,
    ValueType,
)


class TestSignalSchema:
    """Tests for SignalSchema class."""
    
    def test_decode_unsigned(self) -> None:
        """Test decoding unsigned value."""
        signal = SignalSchema(
            name="TestSignal",
            start_bit=0,
            bit_length=8,
        )
        
        data = bytes([0x64, 0, 0, 0, 0, 0, 0, 0])
        value = signal.decode(data)
        
        assert value == 100
    
    def test_decode_with_scale_offset(self) -> None:
        """Test decoding with scale and offset."""
        signal = SignalSchema(
            name="Temperature",
            start_bit=0,
            bit_length=8,
            scale=0.5,
            offset=-40,
        )
        
        data = bytes([200, 0, 0, 0, 0, 0, 0, 0])
        value = signal.decode(data)
        
        assert value == 60.0
    
    def test_encode_value(self) -> None:
        """Test encoding a physical value."""
        signal = SignalSchema(
            name="RPM",
            start_bit=0,
            bit_length=16,
            scale=0.25,
        )
        
        raw = signal.encode(1000)
        assert raw == 4000


class TestMessageSchema:
    """Tests for MessageSchema class."""
    
    def test_create_schema(self) -> None:
        """Test creating a message schema."""
        schema = MessageSchema(
            arbitration_id=0x100,
            name="EngineStatus",
            signals=[
                SignalSchema(name="RPM", start_bit=0, bit_length=16),
                SignalSchema(name="Temp", start_bit=16, bit_length=8),
            ],
        )
        
        assert schema.arbitration_id == 0x100
        assert schema.name == "EngineStatus"
        assert len(schema.signals) == 2
    
    def test_get_signal(self) -> None:
        """Test getting a signal by name."""
        schema = MessageSchema(
            arbitration_id=0x100,
            name="Test",
            signals=[
                SignalSchema(name="Signal1", start_bit=0, bit_length=8),
                SignalSchema(name="Signal2", start_bit=8, bit_length=8),
            ],
        )
        
        signal = schema.get_signal("Signal1")
        assert signal is not None
        assert signal.name == "Signal1"
        
        assert schema.get_signal("NonExistent") is None
    
    def test_add_signal(self) -> None:
        """Test adding a signal to schema."""
        schema = MessageSchema(arbitration_id=0x100, name="Test")
        
        schema.add_signal(SignalSchema(name="NewSignal", start_bit=0, bit_length=8))
        
        assert len(schema.signals) == 1
        assert schema.get_signal("NewSignal") is not None


class TestFrameNormalizer:
    """Tests for FrameNormalizer class."""
    
    @pytest.fixture
    def normalizer(self) -> FrameNormalizer:
        """Create a test normalizer."""
        return FrameNormalizer()
    
    @pytest.fixture
    def engine_schema(self) -> MessageSchema:
        """Create a test engine schema."""
        return MessageSchema(
            arbitration_id=0x100,
            name="EngineStatus",
            signals=[
                SignalSchema(
                    name="RPM",
                    start_bit=0,
                    bit_length=16,
                    scale=1.0,
                    unit="rpm",
                ),
                SignalSchema(
                    name="Temperature",
                    start_bit=16,
                    bit_length=8,
                    scale=1.0,
                    offset=-40,
                    unit="°C",
                ),
            ],
        )
    
    def test_register_schema(
        self,
        normalizer: FrameNormalizer,
        engine_schema: MessageSchema,
    ) -> None:
        """Test registering a schema."""
        normalizer.register_schema(engine_schema)
        
        assert 0x100 in normalizer.registered_ids
        assert normalizer.get_schema(0x100) is engine_schema
    
    def test_normalize_frame(
        self,
        normalizer: FrameNormalizer,
        engine_schema: MessageSchema,
    ) -> None:
        """Test normalizing a frame."""
        normalizer.register_schema(engine_schema)
        
        frame = CANFrame(
            arbitration_id=0x100,
            data=bytes([0xE8, 0x03, 0x5A, 0, 0, 0, 0, 0]),
        )
        
        message = normalizer.normalize(frame)
        
        assert message is not None
        assert message.name == "EngineStatus"
        assert "RPM" in message.signals
        assert "Temperature" in message.signals
    
    def test_normalize_unknown_id(self, normalizer: FrameNormalizer) -> None:
        """Test normalizing frame with unknown ID."""
        frame = CANFrame(arbitration_id=0x500)
        
        message = normalizer.normalize(frame)
        
        assert message is None
        assert 0x500 in normalizer.unknown_ids
    
    def test_unregister_schema(
        self,
        normalizer: FrameNormalizer,
        engine_schema: MessageSchema,
    ) -> None:
        """Test unregistering a schema."""
        normalizer.register_schema(engine_schema)
        normalizer.unregister_schema(0x100)
        
        assert 0x100 not in normalizer.registered_ids
    
    def test_normalize_batch(
        self,
        normalizer: FrameNormalizer,
        engine_schema: MessageSchema,
    ) -> None:
        """Test batch normalization."""
        normalizer.register_schema(engine_schema)
        
        frames = [
            CANFrame(arbitration_id=0x100, data=bytes([0, 0, 0x50, 0, 0, 0, 0, 0])),
            CANFrame(arbitration_id=0x500),
            CANFrame(arbitration_id=0x100, data=bytes([0, 0, 0x60, 0, 0, 0, 0, 0])),
        ]
        
        messages = normalizer.normalize_batch(frames)
        
        assert len(messages) == 2
        assert all(m.arbitration_id == 0x100 for m in messages)
    
    def test_clear_unknown(self, normalizer: FrameNormalizer) -> None:
        """Test clearing unknown IDs."""
        normalizer.normalize(CANFrame(arbitration_id=0x500))
        assert 0x500 in normalizer.unknown_ids
        
        normalizer.clear_unknown()
        assert len(normalizer.unknown_ids) == 0
