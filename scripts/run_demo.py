from __future__ import annotations

import argparse
import time
import json
from pathlib import Path
from datetime import datetime, timezone

from virtual_bus.bus.bus import Bus
from virtual_bus.bus.types import Frame, Signal
from virtual_bus.bus.observer import Observer
from virtual_bus.bus.generator import create_traffic_generator
from virtual_bus.bus.normalizer import Normalizer
from virtual_bus.bus.analyzer import Analyzer


def nice_path(path: Path, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except Exception:
        return str(path)

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
        "--anomaly-rate",
        type=float,
        default=0.001,
        help="Probability per frame (per CAN ID) to inject an ID-specific anomaly (noisy mode only).",
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

    analyzer = Analyzer(artifacts_dir)
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

    meta = {
        "schema_version": 1,
        "tool": "run_demo",
        "created_at": datetime.now(timezone.utc).isoformat(),

        # run config
        "mode": args.mode,
        "profile": args.profile,
        "seed": args.seed,
        "duration_s": args.duration_s,
        "period_ms": args.period_ms,
        "anomaly_rate": (args.anomaly_rate if args.mode == "noisy" else 0.0),

        "mapping": mapping,
    }

    (meta_path := artifacts_dir / "run_meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    normalizer = Normalizer(artifacts_dir, mapping, publish_signal=signal_bus.publish)
    frame_bus.subscribe(normalizer.on_frame)

    gen = create_traffic_generator(
        scenario=args.mode,
        profile=args.profile,
        period_ms=args.period_ms,
        seed=args.seed,
        anomaly_rate=args.anomaly_rate,
    )
    sent = gen.run(frame_bus.publish, duration_s=args.duration_s)

    elapsed = time.perf_counter() - start

    frames_path = artifacts_dir / "frames.jsonl"
    signals_path = artifacts_dir / "signals.jsonl"
    events_path = artifacts_dir / "events.jsonl"

    print("=== Demo complete ===")
    print(f"Mode:             {args.mode}")
    if args.mode == "noisy":
        print(f"Anomaly rate:     {args.anomaly_rate}")
    else :
        print(f"Anomaly rate:     0.0")
    print(f"Profile:          {args.profile}")
    print(f"Seed:             {args.seed}")
    print(f"Frames sent:      {sent}")
    print(f"Frames stored:    {observer.count}  -> {nice_path(frames_path, root)}")
    print(f"Signals stored:   {normalizer.count}  -> {nice_path(signals_path, root)}")
    print(f"Events stored:    {analyzer.count}    -> {nice_path(events_path, root)}")
    print(f"Elapsed time:     {elapsed:.3f} s")


if __name__ == "__main__":
    main()
