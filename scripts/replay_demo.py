from __future__ import annotations

import argparse
import time
from pathlib import Path

from virtual_bus.bus.bus import Bus
from virtual_bus.bus.types import Frame, Signal
from virtual_bus.bus.normalizer import Normalizer
from virtual_bus.bus.analyzer import Analyzer
from virtual_bus.bus.replayer import FrameReplayer


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay a recorded frames.jsonl through the pipeline.")
    parser.add_argument(
        "--mode",
        choices=("clean", "noisy"),
        default="clean",
        help="Which artifacts dataset to replay (default: clean).",
    )
    parser.add_argument(
        "--infile",
        type=Path,
        default=None,
        help="Optional explicit path to frames.jsonl (overrides --mode).",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max frames to replay.")
    parser.add_argument("--speed", type=float, default=1.0, help="Playback speed factor (relative timing only).")
    parser.add_argument(
        "--timing",
        choices=("none", "relative"), # default=relative to mimic real-time playback
        default="relative",
        help="Replay timing mode: 'relative' sleeps based on timestamps; 'none' runs as fast as possible.",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    artifacts_dir = root / "artifacts" / args.mode

    infile = args.infile if args.infile is not None else (artifacts_dir / "frames.jsonl")
    if not infile.exists():
        raise SystemExit(
            f"Input file not found: {infile}\n"
            f"Run: python -m scripts.run_demo --mode {args.mode}\n"
            f"Or pass --infile path/to/frames.jsonl"
        )

    # Output stays within the same mode folder by default
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    frame_bus: Bus[Frame] = Bus()
    signal_bus: Bus[Signal] = Bus()

    analyzer = Analyzer(artifacts_dir, watch_signal="counter")
    signal_bus.subscribe(analyzer.on_signal)

    mapping = {0x123: [("counter", 0, "count")]}
    normalizer = Normalizer(artifacts_dir, mapping, publish_signal=signal_bus.publish)
    frame_bus.subscribe(normalizer.on_frame)

    replayer = FrameReplayer(
        infile,
        timing=args.timing,
        speed=args.speed,
    )

    start = time.perf_counter()
    replayed = replayer.run(frame_bus.publish, limit=args.limit)
    elapsed = time.perf_counter() - start

    normalizer.close()
    analyzer.close()

    print("=== Replay complete ===")
    print(f"Mode:             {args.mode}")
    print(f"Input frames:     {infile}")
    print(f"Frames replayed:  {replayed}")
    print(f"Signals stored:   {normalizer.count} -> {artifacts_dir / 'signals.jsonl'}")
    print(f"Events stored:    {analyzer.count}   -> {artifacts_dir / 'events.jsonl'}")
    print(f"Elapsed time:     {elapsed:.3f} s")


if __name__ == "__main__":
    main()
