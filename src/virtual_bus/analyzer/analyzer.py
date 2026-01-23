"""Timing-aware analysis implementation."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Optional

from virtual_bus.observer.observer import BusObserver, ObservedFrame
from virtual_bus.analyzer.events import (
    AnalysisEvent,
    EventSeverity,
    MissedDeadlineEvent,
    BusSaturationEvent,
    AnomalousRateEvent,
    JitterEvent,
)


@dataclass
class MessageExpectation:
    """Expected timing characteristics for a message."""
    
    arbitration_id: int
    period_ms: float
    tolerance_percent: float = 20.0
    jitter_threshold_ms: float = 5.0
    
    @property
    def min_interval_ms(self) -> float:
        """Minimum acceptable interval."""
        return self.period_ms * (1 - self.tolerance_percent / 100)
    
    @property
    def max_interval_ms(self) -> float:
        """Maximum acceptable interval (deadline)."""
        return self.period_ms * (1 + self.tolerance_percent / 100)


@dataclass
class AnalyzerConfig:
    """Configuration for the timing analyzer."""
    
    bus_saturation_threshold: float = 5000.0
    window_size_seconds: float = 1.0
    enable_deadline_detection: bool = True
    enable_saturation_detection: bool = True
    enable_jitter_detection: bool = True


class TimingAnalyzer:
    """Analyzes CAN traffic for timing-related issues.
    
    The analyzer monitors message timing, detects missed deadlines,
    bus saturation, and other system-level timing anomalies.
    """
    
    def __init__(
        self,
        observer: Optional[BusObserver] = None,
        config: Optional[AnalyzerConfig] = None,
    ) -> None:
        self._observer = observer
        self._config = config or AnalyzerConfig()
        self._expectations: dict[int, MessageExpectation] = {}
        self._events: list[AnalysisEvent] = []
        self._event_callbacks: list[Callable[[AnalysisEvent], None]] = []
        self._last_times: dict[int, float] = {}
        self._window_frames: list[float] = []
        self._intervals: dict[int, list[float]] = defaultdict(list)
        self._is_attached = False
    
    @property
    def events(self) -> list[AnalysisEvent]:
        """List of detected events."""
        return self._events.copy()
    
    @property
    def event_count(self) -> int:
        """Number of detected events."""
        return len(self._events)
    
    def set_expectation(self, expectation: MessageExpectation) -> None:
        """Set timing expectation for a message ID."""
        self._expectations[expectation.arbitration_id] = expectation
    
    def remove_expectation(self, arbitration_id: int) -> None:
        """Remove timing expectation for a message ID."""
        self._expectations.pop(arbitration_id, None)
    
    def add_event_callback(self, callback: Callable[[AnalysisEvent], None]) -> None:
        """Add callback for detected events."""
        self._event_callbacks.append(callback)
    
    def attach(self, observer: BusObserver) -> None:
        """Attach to an observer to receive frames."""
        if self._is_attached:
            self.detach()
        
        self._observer = observer
        self._observer.add_callback(self._on_frame)
        self._is_attached = True
    
    def detach(self) -> None:
        """Detach from the current observer."""
        if self._observer and self._is_attached:
            self._observer.remove_callback(self._on_frame)
            self._is_attached = False
    
    def _emit_event(self, event: AnalysisEvent) -> None:
        """Record and emit an event."""
        self._events.append(event)
        for callback in self._event_callbacks:
            try:
                callback(event)
            except Exception:
                pass
    
    def _on_frame(self, observed: ObservedFrame) -> None:
        """Analyze an observed frame."""
        now = observed.observation_time
        arb_id = observed.frame.arbitration_id
        
        self._window_frames.append(now)
        cutoff = now - self._config.window_size_seconds
        self._window_frames = [t for t in self._window_frames if t > cutoff]
        
        if self._config.enable_saturation_detection:
            self._check_saturation(now)
        
        if arb_id in self._last_times:
            interval_ms = (now - self._last_times[arb_id]) * 1000
            self._intervals[arb_id].append(interval_ms)
            
            if len(self._intervals[arb_id]) > 100:
                self._intervals[arb_id] = self._intervals[arb_id][-100:]
            
            if arb_id in self._expectations:
                expectation = self._expectations[arb_id]
                
                if self._config.enable_deadline_detection:
                    self._check_deadline(arb_id, interval_ms, expectation, now)
                
                if self._config.enable_jitter_detection:
                    self._check_jitter(arb_id, expectation, now)
        
        self._last_times[arb_id] = now
    
    def _check_deadline(
        self,
        arb_id: int,
        interval_ms: float,
        expectation: MessageExpectation,
        timestamp: float,
    ) -> None:
        """Check for missed deadlines."""
        if interval_ms > expectation.max_interval_ms:
            self._emit_event(MissedDeadlineEvent(
                timestamp=timestamp,
                severity=EventSeverity.WARNING,
                message="",
                arbitration_id=arb_id,
                expected_period_ms=expectation.period_ms,
                actual_interval_ms=interval_ms,
            ))
    
    def _check_saturation(self, timestamp: float) -> None:
        """Check for bus saturation."""
        frame_rate = len(self._window_frames) / self._config.window_size_seconds
        
        if frame_rate > self._config.bus_saturation_threshold:
            recent_events = [
                e for e in self._events[-10:]
                if isinstance(e, BusSaturationEvent)
                and timestamp - e.timestamp < 1.0
            ]
            if not recent_events:
                self._emit_event(BusSaturationEvent(
                    timestamp=timestamp,
                    severity=EventSeverity.ERROR,
                    message="",
                    frame_rate=frame_rate,
                    threshold=self._config.bus_saturation_threshold,
                ))
    
    def _check_jitter(
        self,
        arb_id: int,
        expectation: MessageExpectation,
        timestamp: float,
    ) -> None:
        """Check for excessive jitter."""
        intervals = self._intervals.get(arb_id, [])
        if len(intervals) < 5:
            return
        
        recent = intervals[-10:]
        avg = sum(recent) / len(recent)
        max_deviation = max(abs(i - avg) for i in recent)
        
        if max_deviation > expectation.jitter_threshold_ms:
            recent_jitter = [
                e for e in self._events[-20:]
                if isinstance(e, JitterEvent)
                and e.arbitration_id == arb_id
                and timestamp - e.timestamp < 1.0
            ]
            if not recent_jitter:
                self._emit_event(JitterEvent(
                    timestamp=timestamp,
                    severity=EventSeverity.WARNING,
                    message="",
                    arbitration_id=arb_id,
                    jitter_ms=max_deviation,
                    threshold_ms=expectation.jitter_threshold_ms,
                ))
    
    def get_statistics(self, arbitration_id: int) -> Optional[dict[str, float]]:
        """Get timing statistics for a message ID."""
        intervals = self._intervals.get(arbitration_id)
        if not intervals:
            return None
        
        avg = sum(intervals) / len(intervals)
        min_val = min(intervals)
        max_val = max(intervals)
        jitter = max_val - min_val
        
        return {
            "count": len(intervals),
            "average_ms": avg,
            "min_ms": min_val,
            "max_ms": max_val,
            "jitter_ms": jitter,
        }
    
    def clear(self) -> None:
        """Clear all analysis state."""
        self._events.clear()
        self._last_times.clear()
        self._window_frames.clear()
        self._intervals.clear()
    
    def summary(self) -> dict[str, object]:
        """Generate analysis summary."""
        by_severity = defaultdict(int)
        for event in self._events:
            by_severity[event.severity.value] += 1
        
        return {
            "total_events": len(self._events),
            "by_severity": dict(by_severity),
            "monitored_ids": list(self._expectations.keys()),
            "observed_ids": list(self._intervals.keys()),
        }
