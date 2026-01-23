"""Tests for bus observer implementation."""

import asyncio
import pytest
from virtual_bus.core.bus import VirtualCANBus
from virtual_bus.core.frame import CANFrame
from virtual_bus.observer.observer import BusObserver, ObservedFrame


class TestBusObserver:
    """Tests for BusObserver class."""
    
    @pytest.fixture
    def bus(self) -> VirtualCANBus:
        """Create a test bus."""
        return VirtualCANBus("test_bus")
    
    @pytest.fixture
    def observer(self) -> BusObserver:
        """Create a test observer."""
        return BusObserver(buffer_size=100)
    
    def test_create_observer(self, observer: BusObserver) -> None:
        """Test observer creation."""
        assert observer.frame_count == 0
        assert len(observer.buffer) == 0
        assert len(observer.unique_ids) == 0
    
    async def test_attach_detach(self, bus: VirtualCANBus, observer: BusObserver) -> None:
        """Test attaching and detaching from bus."""
        observer.attach(bus)
        assert observer._is_attached
        
        observer.detach()
        assert not observer._is_attached
    
    async def test_observe_frames(self, bus: VirtualCANBus, observer: BusObserver) -> None:
        """Test observing frames."""
        observer.attach(bus)
        
        async with bus:
            await bus.transmit(CANFrame(arbitration_id=0x100, data=bytes([1])))
            await bus.transmit(CANFrame(arbitration_id=0x200, data=bytes([2])))
            await asyncio.sleep(0.1)
        
        assert observer.frame_count == 2
        assert len(observer.buffer) == 2
        assert observer.unique_ids == {0x100, 0x200}
    
    async def test_inter_arrival_time(self, bus: VirtualCANBus, observer: BusObserver) -> None:
        """Test inter-arrival time calculation."""
        observer.attach(bus)
        
        async with bus:
            await bus.transmit(CANFrame(arbitration_id=0x100))
            await asyncio.sleep(0.05)
            await bus.transmit(CANFrame(arbitration_id=0x100))
            await asyncio.sleep(0.1)
        
        frames = observer.get_frames_by_id(0x100)
        assert len(frames) == 2
        
        assert frames[0].inter_arrival_time is None
        assert frames[1].inter_arrival_time is not None
        assert 0.04 < frames[1].inter_arrival_time < 0.1
    
    async def test_statistics(self, bus: VirtualCANBus, observer: BusObserver) -> None:
        """Test per-ID statistics."""
        observer.attach(bus)
        
        async with bus:
            for _ in range(5):
                await bus.transmit(CANFrame(arbitration_id=0x100, data=bytes([0, 0])))
                await asyncio.sleep(0.02)
            await asyncio.sleep(0.1)
        
        stats = observer.statistics
        assert 0x100 in stats
        assert stats[0x100].count == 5
        assert stats[0x100].total_bytes == 10
        assert stats[0x100].average_interval is not None
    
    async def test_buffer_limit(self, bus: VirtualCANBus) -> None:
        """Test buffer size limit."""
        observer = BusObserver(buffer_size=5)
        observer.attach(bus)
        
        async with bus:
            for i in range(10):
                await bus.transmit(CANFrame(arbitration_id=0x100, data=bytes([i])))
            await asyncio.sleep(0.1)
        
        assert len(observer.buffer) == 5
        assert observer.frame_count == 10
    
    async def test_callback(self, bus: VirtualCANBus, observer: BusObserver) -> None:
        """Test observer callback."""
        observer.attach(bus)
        
        received: list[ObservedFrame] = []
        observer.add_callback(lambda f: received.append(f))
        
        async with bus:
            await bus.transmit(CANFrame(arbitration_id=0x100))
            await asyncio.sleep(0.1)
        
        assert len(received) == 1
        assert received[0].frame.arbitration_id == 0x100
    
    async def test_get_frames_by_id(self, bus: VirtualCANBus, observer: BusObserver) -> None:
        """Test filtering frames by ID."""
        observer.attach(bus)
        
        async with bus:
            await bus.transmit(CANFrame(arbitration_id=0x100))
            await bus.transmit(CANFrame(arbitration_id=0x200))
            await bus.transmit(CANFrame(arbitration_id=0x100))
            await asyncio.sleep(0.1)
        
        frames_100 = observer.get_frames_by_id(0x100)
        frames_200 = observer.get_frames_by_id(0x200)
        
        assert len(frames_100) == 2
        assert len(frames_200) == 1
    
    async def test_clear(self, bus: VirtualCANBus, observer: BusObserver) -> None:
        """Test clearing observer state."""
        observer.attach(bus)
        
        async with bus:
            await bus.transmit(CANFrame(arbitration_id=0x100))
            await asyncio.sleep(0.1)
        
        assert observer.frame_count > 0
        
        observer.clear()
        
        assert observer.frame_count == 0
        assert len(observer.buffer) == 0
        assert len(observer.statistics) == 0
    
    def test_summary(self, observer: BusObserver) -> None:
        """Test summary generation."""
        summary = observer.summary()
        
        assert "total_frames" in summary
        assert "unique_ids" in summary
        assert "buffer_size" in summary
        assert "observation_duration" in summary
