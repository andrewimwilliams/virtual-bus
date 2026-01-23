"""Live display for real-time bus monitoring."""

from __future__ import annotations

import asyncio
from collections import deque
from typing import Optional

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.layout import Layout
from rich.panel import Panel

from virtual_bus.observer.observer import BusObserver, ObservedFrame
from virtual_bus.analyzer.analyzer import TimingAnalyzer
from virtual_bus.analyzer.events import AnalysisEvent


class LiveDisplay:
    """Real-time display of bus activity using Rich Live."""
    
    def __init__(
        self,
        observer: Optional[BusObserver] = None,
        analyzer: Optional[TimingAnalyzer] = None,
        max_frames: int = 20,
        max_events: int = 10,
        refresh_rate: float = 4.0,
    ) -> None:
        self._observer = observer
        self._analyzer = analyzer
        self._max_frames = max_frames
        self._max_events = max_events
        self._refresh_rate = refresh_rate
        self._recent_frames: deque[ObservedFrame] = deque(maxlen=max_frames)
        self._recent_events: deque[AnalysisEvent] = deque(maxlen=max_events)
        self._console = Console()
        self._running = False
    
    def attach(
        self,
        observer: BusObserver,
        analyzer: Optional[TimingAnalyzer] = None,
    ) -> None:
        """Attach to observer and analyzer."""
        self._observer = observer
        self._analyzer = analyzer
        
        observer.add_callback(self._on_frame)
        if analyzer:
            analyzer.add_event_callback(self._on_event)
    
    def _on_frame(self, observed: ObservedFrame) -> None:
        """Handle observed frame."""
        self._recent_frames.append(observed)
    
    def _on_event(self, event: AnalysisEvent) -> None:
        """Handle analysis event."""
        self._recent_events.append(event)
    
    def _build_frames_table(self) -> Table:
        """Build the recent frames table."""
        table = Table(title="Recent Frames", expand=True)
        table.add_column("#", style="dim", width=6)
        table.add_column("ID", style="cyan", width=8)
        table.add_column("Data", style="green")
        table.add_column("Δt", style="yellow", width=10)
        
        for observed in self._recent_frames:
            frame = observed.frame
            data_str = " ".join(f"{b:02X}" for b in frame.data)
            interval = observed.inter_arrival_time
            interval_str = f"{interval*1000:.1f}ms" if interval else "-"
            
            table.add_row(
                str(observed.sequence_number),
                f"{frame.arbitration_id:#05x}",
                data_str,
                interval_str,
            )
        
        return table
    
    def _build_stats_table(self) -> Table:
        """Build the statistics table."""
        table = Table(title="Message Statistics", expand=True)
        table.add_column("ID", style="cyan")
        table.add_column("Count", justify="right")
        table.add_column("Rate", justify="right")
        
        if self._observer:
            stats = self._observer.statistics
            for arb_id in sorted(stats.keys())[:10]:
                s = stats[arb_id]
                avg = s.average_interval
                rate = f"{1/avg:.1f}/s" if avg and avg > 0 else "-"
                
                table.add_row(
                    f"{arb_id:#05x}",
                    str(s.count),
                    rate,
                )
        
        return table
    
    def _build_events_panel(self) -> Panel:
        """Build the events panel."""
        lines = []
        for event in self._recent_events:
            id_str = f"[{event.arbitration_id:#x}]" if event.arbitration_id else ""
            lines.append(f"{event.severity.value.upper()} {id_str} {event.message}")
        
        content = "\n".join(lines) if lines else "No events"
        return Panel(content, title="Recent Events")
    
    def _build_layout(self) -> Layout:
        """Build the display layout."""
        layout = Layout()
        
        layout.split_row(
            Layout(name="left", ratio=2),
            Layout(name="right", ratio=1),
        )
        
        layout["left"].split_column(
            Layout(self._build_frames_table(), name="frames"),
        )
        
        layout["right"].split_column(
            Layout(self._build_stats_table(), name="stats"),
            Layout(self._build_events_panel(), name="events"),
        )
        
        return layout
    
    async def run(self) -> None:
        """Run the live display."""
        self._running = True
        
        with Live(
            self._build_layout(),
            console=self._console,
            refresh_per_second=self._refresh_rate,
        ) as live:
            while self._running:
                live.update(self._build_layout())
                await asyncio.sleep(1 / self._refresh_rate)
    
    def stop(self) -> None:
        """Stop the live display."""
        self._running = False
