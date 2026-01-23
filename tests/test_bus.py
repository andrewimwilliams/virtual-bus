"""Tests for virtual CAN bus implementation."""

import asyncio
import pytest
from virtual_bus.core.bus import VirtualCANBus
from virtual_bus.core.frame import CANFrame
from virtual_bus.core.node import CANNode


class TestVirtualCANBus:
    """Tests for VirtualCANBus class."""
    
    @pytest.fixture
    def bus(self) -> VirtualCANBus:
        """Create a test bus."""
        return VirtualCANBus("test_bus")
    
    def test_create_bus(self, bus: VirtualCANBus) -> None:
        """Test bus creation."""
        assert bus.name == "test_bus"
        assert bus.statistics.frames_transmitted == 0
    
    async def test_bus_context_manager(self, bus: VirtualCANBus) -> None:
        """Test bus as async context manager."""
        async with bus:
            assert bus._running
        
        assert not bus._running
    
    async def test_attach_detach_node(self, bus: VirtualCANBus) -> None:
        """Test attaching and detaching nodes."""
        node = CANNode("TestNode")
        
        bus.attach_node(node)
        assert node in bus._nodes
        assert node._bus is bus
        
        bus.detach_node(node)
        assert node not in bus._nodes
        assert node._bus is None
    
    async def test_transmit_frame(self, bus: VirtualCANBus) -> None:
        """Test frame transmission."""
        received_frames: list[CANFrame] = []
        
        def observer(frame: CANFrame) -> None:
            received_frames.append(frame)
        
        bus.add_observer(observer)
        
        async with bus:
            frame = CANFrame(arbitration_id=0x100, data=bytes([0x01, 0x02]))
            await bus.transmit(frame)
            
            await asyncio.sleep(0.1)
        
        assert len(received_frames) == 1
        assert received_frames[0].arbitration_id == 0x100
        assert bus.statistics.frames_transmitted == 1
    
    async def test_multiple_observers(self, bus: VirtualCANBus) -> None:
        """Test multiple observers receive frames."""
        counts = [0, 0]
        
        def observer1(frame: CANFrame) -> None:
            counts[0] += 1
        
        def observer2(frame: CANFrame) -> None:
            counts[1] += 1
        
        bus.add_observer(observer1)
        bus.add_observer(observer2)
        
        async with bus:
            await bus.transmit(CANFrame(arbitration_id=0x100))
            await asyncio.sleep(0.1)
        
        assert counts[0] == 1
        assert counts[1] == 1
    
    async def test_remove_observer(self, bus: VirtualCANBus) -> None:
        """Test removing an observer."""
        count = 0
        
        def observer(frame: CANFrame) -> None:
            nonlocal count
            count += 1
        
        bus.add_observer(observer)
        bus.remove_observer(observer)
        
        async with bus:
            await bus.transmit(CANFrame(arbitration_id=0x100))
            await asyncio.sleep(0.1)
        
        assert count == 0
    
    async def test_statistics_update(self, bus: VirtualCANBus) -> None:
        """Test statistics are updated correctly."""
        async with bus:
            await bus.transmit(CANFrame(arbitration_id=0x100, data=bytes([1, 2, 3])))
            await bus.transmit(CANFrame(arbitration_id=0x200, data=bytes([4, 5])))
            await asyncio.sleep(0.1)
        
        assert bus.statistics.frames_transmitted == 2
        assert bus.statistics.bytes_transmitted == 5
