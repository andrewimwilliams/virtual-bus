"""Analysis event definitions."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class EventSeverity(Enum):
    """Severity level for analysis events."""
    
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AnalysisEvent:
    """Base class for analysis events."""
    
    timestamp: float
    severity: EventSeverity
    message: str
    arbitration_id: Optional[int] = None
    
    def __repr__(self) -> str:
        id_str = f"[{self.arbitration_id:#x}]" if self.arbitration_id else ""
        return f"{self.severity.value.upper()}{id_str}: {self.message}"


@dataclass
class MissedDeadlineEvent(AnalysisEvent):
    """Event indicating a message missed its expected deadline."""
    
    expected_period_ms: float = 0.0
    actual_interval_ms: float = 0.0
    
    def __post_init__(self) -> None:
        if not self.message:
            self.message = (
                f"Missed deadline: expected {self.expected_period_ms:.1f}ms, "
                f"got {self.actual_interval_ms:.1f}ms"
            )


@dataclass
class BusSaturationEvent(AnalysisEvent):
    """Event indicating potential bus saturation."""
    
    frame_rate: float = 0.0
    threshold: float = 0.0
    
    def __post_init__(self) -> None:
        if not self.message:
            self.message = (
                f"Bus saturation: {self.frame_rate:.1f} frames/sec "
                f"exceeds threshold {self.threshold:.1f}"
            )


@dataclass
class AnomalousRateEvent(AnalysisEvent):
    """Event indicating an unusual message rate."""
    
    expected_rate: float = 0.0
    actual_rate: float = 0.0
    
    def __post_init__(self) -> None:
        if not self.message:
            self.message = (
                f"Anomalous rate: expected {self.expected_rate:.1f}/sec, "
                f"got {self.actual_rate:.1f}/sec"
            )


@dataclass
class JitterEvent(AnalysisEvent):
    """Event indicating excessive timing jitter."""
    
    jitter_ms: float = 0.0
    threshold_ms: float = 0.0
    
    def __post_init__(self) -> None:
        if not self.message:
            self.message = (
                f"Excessive jitter: {self.jitter_ms:.2f}ms "
                f"exceeds threshold {self.threshold_ms:.2f}ms"
            )
