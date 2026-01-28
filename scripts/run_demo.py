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
    parser.add_argument(
        "--profile",
        choices=("single", "multi"),
        default="single",
        help="Traffic profile: single CAN ID (counter only) or multi CAN IDs (richer signals).",
    )
    parser.add_argument(
        "--p-counter-jump",
        type=float,
        default=0.001,
        help="Probability per eligible counter frame to inject a counter jump (noisy mode only).",
    )
    parser.add_argument("--seed", type=int, default=None, help="Optional RNG seed (useful for reproducible noisy runs).")
    parser.add_argument("--duration-s", type=float, default=2.5, help="Demo duration in seconds.")
    parser.add_argument("--period-ms", type=int, default=20, help="Generator period in milliseconds.")
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

    if args.profile == "single":
        mapping = {0x123: [("counter", 0, "count")]}
    else:
        # Matches the multi-source generator layout:
        # - counter: byte 0
        # - temperature: bytes 0-1 (little endian, deci-degC)
        # - voltage: bytes 0-1 (little endian, mV)
        mapping = {
            0x123: [("counter", 0, "count")],                 # old format still ok
            0x124: [("temperature_deciC", "u16_le", 0, "deciC")],
            0x125: [("voltage_mv", "u16_le", 0, "mV")],
        }

    normalizer = Normalizer(artifacts_dir, mapping, publish_signal=signal_bus.publish)
    frame_bus.subscribe(normalizer.on_frame)

    gen = create_traffic_generator(
        scenario=args.mode,
        profile=args.profile,
        period_ms=args.period_ms,
        seed=args.seed,
        p_counter_jump=args.p_counter_jump,
    )
    sent = gen.run(frame_bus.publish, duration_s=args.duration_s)

    elapsed = time.perf_counter() - start

    print("=== Demo complete ===")
    print(f"Mode:             {args.mode}")
    if args.mode == "noisy":
        print(f"Anomaly rate:     {args.p_counter_jump}")
    else :
        print(f"Anomaly rate:     {"0"}")
    print(f"Profile:          {args.profile}")
    print(f"Seed:             {args.seed}")
    print(f"Frames sent:      {sent}")
    print(f"Frames stored:    {observer.count}  -> {artifacts_dir / 'frames.jsonl'}")
    print(f"Signals stored:   {normalizer.count} -> {artifacts_dir / 'signals.jsonl'}")
    print(f"Events stored:    {analyzer.count}   -> {artifacts_dir / 'events.jsonl'}")
    print(f"Elapsed time:     {elapsed:.3f} s")


if __name__ == "__main__":
    main()
