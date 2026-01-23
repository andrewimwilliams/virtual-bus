"""Console-based visualization using Rich."""

from __future__ import annotations

from collections import defaultdict
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from virtual_bus.core.frame import CANFrame
from virtual_bus.observer.observer import BusObserver, ObservedFrame, MessageStatistics
from virtual_bus.analyzer.analyzer import TimingAnalyzer
from virtual_bus.analyzer.events import AnalysisEvent, EventSeverity
from virtual_bus.normalizer.normalizer import FrameNormalizer, NormalizedMessage


class ConsoleVisualizer:
    """Renders CAN bus data to the console using Rich."""
    
    def __init__(self, console: Optional[Console] = None) -> None:
        self.console = console or Console()
    
    def print_frame(self, frame: CANFrame) -> None:
        """Print a single CAN frame."""
        id_str = f"{frame.arbitration_id:#05x}"
        data_str = " ".join(f"{b:02X}" for b in frame.data)
        
        self.console.print(
            f"[cyan]{id_str}[/cyan] "
            f"[dim]DLC={frame.effective_dlc}[/dim] "
            f"[green]{data_str}[/green]"
        )
    
    def print_observed_frame(self, observed: ObservedFrame) -> None:
        """Print an observed frame with metadata."""
        frame = observed.frame
        id_str = f"{frame.arbitration_id:#05x}"
        data_str = " ".join(f"{b:02X}" for b in frame.data)
        
        interval_str = ""
        if observed.inter_arrival_time is not None:
            interval_str = f" [yellow]Δ{observed.inter_arrival_time*1000:.1f}ms[/yellow]"
        
        self.console.print(
            f"[dim]#{observed.sequence_number:05d}[/dim] "
            f"[cyan]{id_str}[/cyan] "
            f"[green]{data_str}[/green]"
            f"{interval_str}"
        )
    
    def print_normalized(self, message: NormalizedMessage) -> None:
        """Print a normalized message."""
        signals = " | ".join(
            f"{s.name}={s.physical_value:.2f}{s.unit}"
            for s in message.signals.values()
        )
        
        self.console.print(
            f"[bold cyan]{message.name}[/bold cyan] "
            f"[dim][{message.arbitration_id:#x}][/dim] "
            f"[green]{signals}[/green]"
        )
    
    def print_event(self, event: AnalysisEvent) -> None:
        """Print an analysis event."""
        color = {
            EventSeverity.INFO: "blue",
            EventSeverity.WARNING: "yellow",
            EventSeverity.ERROR: "red",
            EventSeverity.CRITICAL: "bold red",
        }.get(event.severity, "white")
        
        id_str = f"[{event.arbitration_id:#x}]" if event.arbitration_id else ""
        
        self.console.print(
            f"[{color}]{event.severity.value.upper()}[/{color}] "
            f"[cyan]{id_str}[/cyan] "
            f"{event.message}"
        )
    
    def print_statistics_table(
        self,
        statistics: dict[int, MessageStatistics],
    ) -> None:
        """Print a table of message statistics."""
        table = Table(title="Message Statistics")
        
        table.add_column("ID", style="cyan")
        table.add_column("Count", justify="right")
        table.add_column("Bytes", justify="right")
        table.add_column("Avg Interval", justify="right")
        table.add_column("Min", justify="right")
        table.add_column("Max", justify="right")
        
        for arb_id in sorted(statistics.keys()):
            stats = statistics[arb_id]
            avg = stats.average_interval
            
            table.add_row(
                f"{arb_id:#05x}",
                str(stats.count),
                str(stats.total_bytes),
                f"{avg*1000:.1f}ms" if avg else "-",
                f"{stats.min_interval*1000:.1f}ms" if stats.min_interval else "-",
                f"{stats.max_interval*1000:.1f}ms" if stats.max_interval else "-",
            )
        
        self.console.print(table)
    
    def print_observer_summary(self, observer: BusObserver) -> None:
        """Print observer summary."""
        summary = observer.summary()
        
        panel = Panel(
            f"Total Frames: {summary['total_frames']}\n"
            f"Unique IDs: {summary['unique_ids']}\n"
            f"Buffer Size: {summary['buffer_size']}\n"
            f"Duration: {summary['observation_duration']:.2f}s",
            title="Observer Summary",
        )
        self.console.print(panel)
    
    def print_analyzer_summary(self, analyzer: TimingAnalyzer) -> None:
        """Print analyzer summary."""
        summary = analyzer.summary()
        
        by_sev = summary.get("by_severity", {})
        sev_str = ", ".join(f"{k}: {v}" for k, v in by_sev.items())
        
        panel = Panel(
            f"Total Events: {summary['total_events']}\n"
            f"By Severity: {sev_str or 'none'}\n"
            f"Monitored IDs: {len(summary.get('monitored_ids', []))}\n"
            f"Observed IDs: {len(summary.get('observed_ids', []))}",
            title="Analyzer Summary",
        )
        self.console.print(panel)
