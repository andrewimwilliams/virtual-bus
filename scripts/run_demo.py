from __future__ import annotations

from pathlib import Path

from virtual_bus.bus.bus import Bus
from virtual_bus.bus.types import Frame, Signal
from virtual_bus.bus.observer import Observer
from virtual_bus.bus.generator import TrafficGenerator
from virtual_bus.bus.normalizer import Normalizer
from virtual_bus.bus.analyzer import Analyzer

import time


def main() -> None:
    start = time.perf_counter()
    root = Path(__file__).resolve().parents[1]
    artifacts_dir = root / "artifacts"

    frame_bus: Bus[Frame] = Bus()
    signal_bus: Bus[Signal] = Bus()

    # Raw frame capture
    observer = Observer(artifacts_dir)
    frame_bus.subscribe(observer.on_frame)

    # Analyzer subscribes to signals
    analyzer = Analyzer(artifacts_dir, watch_signal="counter")
    signal_bus.subscribe(analyzer.on_signal)

    # Normalizer decodes frames into signals
    mapping = {
        0x123: [("counter", 0, "count")],
    }
    normalizer = Normalizer(artifacts_dir, mapping, publish_signal=signal_bus.publish)
    frame_bus.subscribe(normalizer.on_frame)

    # Generate traffic
    gen = TrafficGenerator(can_id=0x123, period_ms=20, fault_at=80)
    sent = gen.run(frame_bus.publish, duration_s=2.5)

    elapsed = time.perf_counter() - start

    print("=== Demo complete ===")
    print(f"Frames sent:    {sent}")
    print(f"Frames stored:  {observer.count}  -> artifacts/frames.jsonl")
    print(f"Signals stored: {normalizer.count} -> artifacts/signals.jsonl")
    print(f"Events stored:  {analyzer.count}   -> artifacts/events.jsonl")
    print(f"Elapsed time:   {elapsed:.3f} s") 


if __name__ == "__main__":
    main()
