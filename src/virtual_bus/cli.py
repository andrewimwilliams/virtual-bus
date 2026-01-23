"""Command-line interface for Virtual Bus."""

import asyncio
import time
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from virtual_bus.core.bus import VirtualCANBus
from virtual_bus.core.node import CANNode, MessageConfig
from virtual_bus.core.frame import CANFrame
from virtual_bus.observer.observer import BusObserver, ObservedFrame
from virtual_bus.analyzer.analyzer import TimingAnalyzer, MessageExpectation, AnalyzerConfig
from virtual_bus.normalizer.normalizer import FrameNormalizer
from virtual_bus.normalizer.schema import MessageSchema, SignalSchema
from virtual_bus.recorder.recorder import TrafficRecorder
from virtual_bus.recorder.player import TrafficPlayer
from virtual_bus.visualization.console import ConsoleVisualizer


console = Console()


@click.group()
@click.version_option(version="0.1.0")
def main() -> None:
    """Virtual Bus - CAN traffic simulation and analysis."""
    pass


@main.command()
@click.option("--duration", "-d", default=5.0, help="Simulation duration in seconds")
@click.option("--nodes", "-n", default=3, help="Number of simulated nodes")
@click.option("--period", "-p", default=100, help="Base message period in ms")
def simulate(duration: float, nodes: int, period: int) -> None:
    """Run a basic CAN bus simulation."""
    console.print(f"[bold]Starting simulation[/bold] ({nodes} nodes, {duration}s)")
    
    asyncio.run(_run_simulation(duration, nodes, period))


async def _run_simulation(duration: float, num_nodes: int, period: int) -> None:
    """Run the simulation asynchronously."""
    bus = VirtualCANBus("vcan0")
    observer = BusObserver(buffer_size=10000)
    visualizer = ConsoleVisualizer(console)
    
    observer.attach(bus)
    
    sim_nodes: list[CANNode] = []
    for i in range(num_nodes):
        node = CANNode(f"Node{i}", node_id=i)
        
        def make_generator(node_id: int) -> callable:
            counter = 0
            def gen() -> bytes:
                nonlocal counter
                counter += 1
                return bytes([node_id, counter & 0xFF, 0, 0, 0, 0, 0, 0])
            return gen
        
        node.add_periodic_message(MessageConfig(
            arbitration_id=0x100 + i * 0x10,
            period_ms=period + i * 20,
            data_generator=make_generator(i),
        ))
        
        bus.attach_node(node)
        sim_nodes.append(node)
    
    async with bus:
        for node in sim_nodes:
            await node.start()
        
        console.print("[green]Simulation running...[/green]")
        await asyncio.sleep(duration)
        
        for node in sim_nodes:
            await node.stop()
    
    observer.detach()
    
    console.print("\n[bold]Simulation Complete[/bold]")
    visualizer.print_observer_summary(observer)
    visualizer.print_statistics_table(observer.statistics)


@main.command()
@click.argument("recording_file", type=click.Path(exists=True))
@click.option("--speed", "-s", default=1.0, help="Playback speed factor")
def replay(recording_file: str, speed: float) -> None:
    """Replay a recorded CAN traffic file."""
    console.print(f"[bold]Replaying[/bold] {recording_file} at {speed}x speed")
    
    asyncio.run(_run_replay(Path(recording_file), speed))


async def _run_replay(path: Path, speed: float) -> None:
    """Run replay asynchronously."""
    bus = VirtualCANBus("vcan0")
    observer = BusObserver()
    player = TrafficPlayer(bus, speed_factor=speed)
    visualizer = ConsoleVisualizer(console)
    
    observer.attach(bus)
    
    metadata = player.load(path)
    console.print(f"Loaded {metadata.frame_count} frames, duration: {metadata.duration:.2f}s")
    
    async with bus:
        await player.play()
        
        while player.state.value == "playing":
            progress = player.progress
            console.print(
                f"\rProgress: {progress.progress_percent:.1f}% "
                f"({progress.current_frame}/{progress.total_frames})",
                end="",
            )
            await asyncio.sleep(0.1)
    
    console.print("\n[bold]Replay Complete[/bold]")
    visualizer.print_observer_summary(observer)


@main.command()
@click.option("--output", "-o", required=True, type=click.Path(), help="Output file path")
@click.option("--duration", "-d", default=10.0, help="Recording duration in seconds")
def record(output: str, duration: float) -> None:
    """Record simulated CAN traffic to a file."""
    console.print(f"[bold]Recording[/bold] to {output} for {duration}s")
    
    asyncio.run(_run_record(Path(output), duration))


async def _run_record(path: Path, duration: float) -> None:
    """Run recording asynchronously."""
    bus = VirtualCANBus("vcan0")
    observer = BusObserver()
    recorder = TrafficRecorder(observer)
    
    observer.attach(bus)
    
    node = CANNode("TestNode", node_id=0)
    counter = 0
    def gen() -> bytes:
        nonlocal counter
        counter += 1
        return bytes([counter & 0xFF, 0, 0, 0, 0, 0, 0, 0])
    
    node.add_periodic_message(MessageConfig(
        arbitration_id=0x100,
        period_ms=100,
        data_generator=gen,
    ))
    bus.attach_node(node)
    
    recorder.start(description=f"Recording for {duration}s")
    
    async with bus:
        await node.start()
        await asyncio.sleep(duration)
        await node.stop()
    
    metadata = recorder.stop()
    recorder.save(path)
    
    console.print(f"[green]Recorded {metadata.frame_count} frames[/green]")
    console.print(f"Duration: {metadata.duration:.2f}s")
    console.print(f"Saved to: {path}")


@main.command()
@click.argument("recording_file", type=click.Path(exists=True))
def analyze(recording_file: str) -> None:
    """Analyze a recorded CAN traffic file."""
    console.print(f"[bold]Analyzing[/bold] {recording_file}")
    
    asyncio.run(_run_analyze(Path(recording_file)))


async def _run_analyze(path: Path) -> None:
    """Run analysis asynchronously."""
    bus = VirtualCANBus("vcan0")
    observer = BusObserver()
    analyzer = TimingAnalyzer(config=AnalyzerConfig(
        enable_deadline_detection=True,
        enable_saturation_detection=True,
        enable_jitter_detection=True,
    ))
    player = TrafficPlayer(bus)
    visualizer = ConsoleVisualizer(console)
    
    observer.attach(bus)
    analyzer.attach(observer)
    
    metadata = player.load(path)
    
    analyzer.set_expectation(MessageExpectation(
        arbitration_id=0x100,
        period_ms=100,
        tolerance_percent=20,
    ))
    
    async with bus:
        count = await player.play_instant()
    
    console.print(f"\n[bold]Analysis Complete[/bold] ({count} frames)")
    visualizer.print_observer_summary(observer)
    visualizer.print_analyzer_summary(analyzer)
    
    if analyzer.events:
        console.print("\n[bold]Detected Events:[/bold]")
        for event in analyzer.events[:20]:
            visualizer.print_event(event)


@main.command()
def demo() -> None:
    """Run a demonstration of all features."""
    console.print("[bold cyan]Virtual Bus Demo[/bold cyan]\n")
    
    asyncio.run(_run_demo())


async def _run_demo() -> None:
    """Run the demo asynchronously."""
    visualizer = ConsoleVisualizer(console)
    
    console.print("[bold]1. Creating Virtual Bus[/bold]")
    bus = VirtualCANBus("vcan0")
    
    console.print("[bold]2. Setting up Observer[/bold]")
    observer = BusObserver(buffer_size=1000)
    observer.attach(bus)
    
    console.print("[bold]3. Setting up Analyzer[/bold]")
    analyzer = TimingAnalyzer()
    analyzer.attach(observer)
    analyzer.set_expectation(MessageExpectation(
        arbitration_id=0x100,
        period_ms=50,
        tolerance_percent=30,
    ))
    
    console.print("[bold]4. Creating Nodes[/bold]")
    
    engine_node = CANNode("EngineECU", node_id=1)
    counter = 0
    def engine_gen() -> bytes:
        nonlocal counter
        counter += 1
        rpm = 3000 + (counter % 100) * 10
        return bytes([
            rpm & 0xFF,
            (rpm >> 8) & 0xFF,
            50,
            0, 0, 0, 0, 0
        ])
    
    engine_node.add_periodic_message(MessageConfig(
        arbitration_id=0x100,
        period_ms=50,
        data_generator=engine_gen,
        jitter_ms=5,
    ))
    bus.attach_node(engine_node)
    
    console.print("[bold]5. Setting up Normalizer[/bold]")
    normalizer = FrameNormalizer()
    normalizer.register_schema(MessageSchema(
        arbitration_id=0x100,
        name="EngineStatus",
        signals=[
            SignalSchema(name="RPM", start_bit=0, bit_length=16, scale=1.0, unit="rpm"),
            SignalSchema(name="Temp", start_bit=16, bit_length=8, scale=1.0, offset=-40, unit="°C"),
        ],
    ))
    
    console.print("[bold]6. Running Simulation (3 seconds)[/bold]\n")
    
    frame_count = 0
    def on_frame(observed: ObservedFrame) -> None:
        nonlocal frame_count
        frame_count += 1
        if frame_count <= 5:
            visualizer.print_observed_frame(observed)
            
            normalized = normalizer.normalize(observed.frame)
            if normalized:
                visualizer.print_normalized(normalized)
            console.print()
    
    observer.add_callback(on_frame)
    
    async with bus:
        await engine_node.start()
        await asyncio.sleep(3)
        await engine_node.stop()
    
    console.print(f"\n[bold]7. Results[/bold]")
    console.print(f"Total frames: {observer.frame_count}")
    
    visualizer.print_statistics_table(observer.statistics)
    visualizer.print_analyzer_summary(analyzer)
    
    if analyzer.events:
        console.print("\n[bold]Detected Events (first 5):[/bold]")
        for event in analyzer.events[:5]:
            visualizer.print_event(event)
    
    console.print("\n[green]Demo complete![/green]")


if __name__ == "__main__":
    main()
