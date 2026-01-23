"""Tests for CAN node implementation."""

import asyncio
import pytest
from virtual_bus.core.bus import VirtualCANBus
from virtual_bus.core.node import CANNode, MessageConfig, FaultConfig
from virtual_bus.core.frame import CANFrame


class TestCANNode:
    """Tests for CANNode class."""
    
    @pytest.fixture
    def bus(self) -> VirtualCANBus:
        """Create a test bus."""
        return VirtualCANBus("test_bus")
    
    @pytest.fixture
    def node(self) -> CANNode:
        """Create a test node."""
        return CANNode("TestNode", node_id=1)
    
    def test_create_node(self, node: CANNode) -> None:
        """Test node creation."""
        assert node.name == "TestNode"
        assert node.node_id == 1
        assert not node.is_connected
    
    def test_node_statistics(self, node: CANNode) -> None:
        """Test node statistics initialization."""
        stats = node.statistics
        assert stats["frames_sent"] == 0
        assert stats["frames_received"] == 0
        assert stats["frames_dropped"] == 0
    
    async def test_node_connection(self, bus: VirtualCANBus, node: CANNode) -> None:
        """Test node connection to bus."""
        assert not node.is_connected
        
        bus.attach_node(node)
        assert node.is_connected
        
        bus.detach_node(node)
        assert not node.is_connected
    
    async def test_periodic_message(self, bus: VirtualCANBus) -> None:
        """Test periodic message transmission."""
        node = CANNode("TestNode")
        
        counter = 0
        def gen() -> bytes:
            nonlocal counter
            counter += 1
            return bytes([counter])
        
        node.add_periodic_message(MessageConfig(
            arbitration_id=0x100,
            period_ms=50,
            data_generator=gen,
        ))
        
        bus.attach_node(node)
        
        received: list[CANFrame] = []
        bus.add_observer(lambda f: received.append(f))
        
        async with bus:
            await node.start()
            await asyncio.sleep(0.2)
            await node.stop()
        
        assert len(received) >= 3
        assert all(f.arbitration_id == 0x100 for f in received)
    
    async def test_receive_callback(self, bus: VirtualCANBus) -> None:
        """Test receive callback."""
        node = CANNode("TestNode")
        bus.attach_node(node)
        
        received: list[CANFrame] = []
        node.add_receive_callback(lambda f: received.append(f))
        
        async with bus:
            frame = CANFrame(arbitration_id=0x200, data=bytes([0xAB]))
            await bus.transmit(frame)
            await asyncio.sleep(0.1)
        
        assert len(received) == 1
        assert received[0].arbitration_id == 0x200
    
    async def test_receive_filter(self, bus: VirtualCANBus) -> None:
        """Test receive filter."""
        node = CANNode("TestNode")
        bus.attach_node(node)
        
        node.set_filter({0x100})
        
        received: list[CANFrame] = []
        node.add_receive_callback(lambda f: received.append(f))
        
        async with bus:
            await bus.transmit(CANFrame(arbitration_id=0x100))
            await bus.transmit(CANFrame(arbitration_id=0x200))
            await asyncio.sleep(0.1)
        
        assert len(received) == 1
        assert received[0].arbitration_id == 0x100
    
    async def test_fault_drop(self, bus: VirtualCANBus) -> None:
        """Test fault injection - drop frames."""
        node = CANNode(
            "TestNode",
            fault_config=FaultConfig(drop_probability=1.0),
        )
        bus.attach_node(node)
        
        received: list[CANFrame] = []
        bus.add_observer(lambda f: received.append(f))
        
        async with bus:
            await node.start()
            frame = CANFrame(arbitration_id=0x100)
            result = await node.transmit(frame)
            await asyncio.sleep(0.1)
        
        assert not result
        assert node.statistics["frames_dropped"] == 1
    
    async def test_node_context_manager(self, bus: VirtualCANBus) -> None:
        """Test node as async context manager."""
        node = CANNode("TestNode")
        node.add_periodic_message(MessageConfig(
            arbitration_id=0x100,
            period_ms=100,
            data_generator=lambda: bytes([0]),
        ))
        bus.attach_node(node)
        
        async with bus:
            async with node:
                assert node._running
            assert not node._running
