# scripts/run_demo.py
from __future__ import annotations

import argparse
import time
from pathlib import Path

from virtual_bus.bus.bus import Bus
from virtual_bus.bus.types import Frame, Signal
from virtual_bus.bus.observer import Observer
from virtual_bus.bus.generator import create_traffic_generator
from virtual_bus.bus.normalizer import Normalizer
from virtual_bus.bus.analyzer import Analyzer


def main() -> None:
    parser = argparse.ArgumentParser(description="Run virtual-bus demo pipeline.")
    parser.add_argument(
        "--mode",
        choices=("clean", "noisy"),
        default="clean",
        help="Choose whether to generate clean or noisy traffic (default: clean).",
    )
    parser.add_argument("--duration-s", type=float, default=2.5, help="Demo duration in seconds.")
    parser.add_argument("--period-ms", type=int, default=20, help="Generator period in milliseconds.")
    parser.add_argument(
        "--fault-at",
        type=int,
        default=None,
        help="Optional frame index at which to inject a counter jump (overrides scenario default).",
    )
    args = parser.parse_args()

    start = time.perf_counter()
    root = Path(__file__).resolve().parents[1]
    artifacts_dir = root / "artifacts" / args.mode
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    frame_bus: Bus[Frame] = Bus()
    signal_bus: Bus[Signal] = Bus()

    observer = Observer(artifacts_dir)
    frame_bus.subscribe(observer.on_frame)

    analyzer = Analyzer(artifacts_dir, watch_signal="counter")
    signal_bus.subscribe(analyzer.on_signal)

    mapping = {0x123: [("counter", 0, "count")]}
    normalizer = Normalizer(artifacts_dir, mapping, publish_signal=signal_bus.publish)
    frame_bus.subscribe(normalizer.on_frame)

    gen = create_traffic_generator(
        scenario=args.mode,
        can_id=0x123,
        period_ms=args.period_ms,
        fault_at=args.fault_at,
    )
    sent = gen.run(frame_bus.publish, duration_s=args.duration_s)

    elapsed = time.perf_counter() - start

    print("=== Demo complete ===")
    print(f"Mode:          {args.mode}")
    print(f"Frames sent:   {sent}")
    print(f"Frames stored: {observer.count}  -> {artifacts_dir / 'frames.jsonl'}")
    print(f"Signals stored:{normalizer.count} -> {artifacts_dir / 'signals.jsonl'}")
    print(f"Events stored: {analyzer.count}   -> {artifacts_dir / 'events.jsonl'}")
    print(f"Elapsed time:  {elapsed:.3f} s")


if __name__ == "__main__":
    main()
