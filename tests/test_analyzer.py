"""Tests for timing analyzer."""

import asyncio
import pytest
from virtual_bus.core.bus import VirtualCANBus
from virtual_bus.core.frame import CANFrame
from virtual_bus.observer.observer import BusObserver
from virtual_bus.analyzer.analyzer import (
    TimingAnalyzer,
    MessageExpectation,
    AnalyzerConfig,
)
from virtual_bus.analyzer.events import (
    MissedDeadlineEvent,
    JitterEvent,
    EventSeverity,
)


class TestMessageExpectation:
    """Tests for MessageExpectation class."""
    
    def test_interval_bounds(self) -> None:
        """Test min/max interval calculation."""
        expectation = MessageExpectation(
            arbitration_id=0x100,
            period_ms=100,
            tolerance_percent=20,
        )
        
        assert expectation.min_interval_ms == 80
        assert expectation.max_interval_ms == 120


class TestTimingAnalyzer:
    """Tests for TimingAnalyzer class."""
    
    @pytest.fixture
    def bus(self) -> VirtualCANBus:
        """Create a test bus."""
        return VirtualCANBus("test_bus")
    
    @pytest.fixture
    def observer(self) -> BusObserver:
        """Create a test observer."""
        return BusObserver()
    
    @pytest.fixture
    def analyzer(self) -> TimingAnalyzer:
        """Create a test analyzer."""
        return TimingAnalyzer(config=AnalyzerConfig(
            bus_saturation_threshold=1000,
            enable_deadline_detection=True,
            enable_jitter_detection=True,
        ))
    
    def test_create_analyzer(self, analyzer: TimingAnalyzer) -> None:
        """Test analyzer creation."""
        assert analyzer.event_count == 0
        assert len(analyzer.events) == 0
    
    def test_set_expectation(self, analyzer: TimingAnalyzer) -> None:
        """Test setting message expectation."""
        expectation = MessageExpectation(
            arbitration_id=0x100,
            period_ms=100,
        )
        
        analyzer.set_expectation(expectation)
        
        summary = analyzer.summary()
        assert 0x100 in summary["monitored_ids"]
    
    async def test_attach_detach(
        self,
        observer: BusObserver,
        analyzer: TimingAnalyzer,
    ) -> None:
        """Test attaching and detaching from observer."""
        analyzer.attach(observer)
        assert analyzer._is_attached
        
        analyzer.detach()
        assert not analyzer._is_attached
    
    async def test_detect_missed_deadline(
        self,
        bus: VirtualCANBus,
        observer: BusObserver,
        analyzer: TimingAnalyzer,
    ) -> None:
        """Test missed deadline detection."""
        observer.attach(bus)
        analyzer.attach(observer)
        
        analyzer.set_expectation(MessageExpectation(
            arbitration_id=0x100,
            period_ms=50,
            tolerance_percent=20,
        ))
        
        async with bus:
            await bus.transmit(CANFrame(arbitration_id=0x100))
            await asyncio.sleep(0.2)
            await bus.transmit(CANFrame(arbitration_id=0x100))
            await asyncio.sleep(0.1)
        
        deadline_events = [
            e for e in analyzer.events
            if isinstance(e, MissedDeadlineEvent)
        ]
        
        assert len(deadline_events) >= 1
    
    async def test_event_callback(
        self,
        bus: VirtualCANBus,
        observer: BusObserver,
        analyzer: TimingAnalyzer,
    ) -> None:
        """Test event callback."""
        observer.attach(bus)
        analyzer.attach(observer)
        
        received_events: list = []
        analyzer.add_event_callback(lambda e: received_events.append(e))
        
        analyzer.set_expectation(MessageExpectation(
            arbitration_id=0x100,
            period_ms=10,
            tolerance_percent=10,
        ))
        
        async with bus:
            await bus.transmit(CANFrame(arbitration_id=0x100))
            await asyncio.sleep(0.1)
            await bus.transmit(CANFrame(arbitration_id=0x100))
            await asyncio.sleep(0.1)
        
        assert len(received_events) >= 1
    
    async def test_get_statistics(
        self,
        bus: VirtualCANBus,
        observer: BusObserver,
        analyzer: TimingAnalyzer,
    ) -> None:
        """Test getting timing statistics."""
        observer.attach(bus)
        analyzer.attach(observer)
        
        async with bus:
            for _ in range(5):
                await bus.transmit(CANFrame(arbitration_id=0x100))
                await asyncio.sleep(0.02)
            await asyncio.sleep(0.1)
        
        stats = analyzer.get_statistics(0x100)
        
        assert stats is not None
        assert stats["count"] >= 4
        assert "average_ms" in stats
        assert "jitter_ms" in stats
    
    def test_clear(self, analyzer: TimingAnalyzer) -> None:
        """Test clearing analyzer state."""
        analyzer._events.append(MissedDeadlineEvent(
            timestamp=0,
            severity=EventSeverity.WARNING,
            message="test",
        ))
        
        analyzer.clear()
        
        assert analyzer.event_count == 0
    
    def test_summary(self, analyzer: TimingAnalyzer) -> None:
        """Test summary generation."""
        analyzer.set_expectation(MessageExpectation(
            arbitration_id=0x100,
            period_ms=100,
        ))
        
        summary = analyzer.summary()
        
        assert "total_events" in summary
        assert "by_severity" in summary
        assert "monitored_ids" in summary
