from __future__ import annotations

from pathlib import Path
import argparse
import json

from virtual_bus.bus.bus import Bus
from virtual_bus.bus.types import Frame, Signal
from virtual_bus.bus.replayer import FrameReplayer
from virtual_bus.bus.normalizer import Normalizer
from virtual_bus.bus.analyzer import Analyzer

import time


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--infile", default="artifacts/frames.jsonl")
    parser.add_argument("--timing", choices=["none", "relative"], default="none")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    start_wall = time.perf_counter()

    root = Path(__file__).resolve().parents[1]
    infile = (root / args.infile).resolve()
    artifacts_dir = root / "artifacts"

    frame_bus: Bus[Frame] = Bus()
    signal_bus: Bus[Signal] = Bus()

    analyzer = Analyzer(artifacts_dir, watch_signal="counter")
    signal_bus.subscribe(analyzer.on_signal)

    mapping = {
        0x123: [("counter", 0, "count")],
    }
    normalizer = Normalizer(artifacts_dir, mapping, publish_signal=signal_bus.publish)
    frame_bus.subscribe(normalizer.on_frame)

    replayer = FrameReplayer(infile, timing=args.timing, speed=args.speed)
    replayed = replayer.run(frame_bus.publish, limit=args.limit)

    elapsed_wall = time.perf_counter() - start_wall

    # Compute recorded time span
    recorded_span_s = None
    if replayed > 1:
        # Re-read cheaply
        first_ts = None
        last_ts = None
        with infile.open("r", encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                ts = d["timestamp_ns"]
                if first_ts is None:
                    first_ts = ts
                last_ts = ts

        if first_ts is not None and last_ts is not None:
            recorded_span_s = (last_ts - first_ts) / 1e9

    normalizer.close()
    analyzer.close()

    print("=== Replay complete ===")
    print(f"Frames replayed: {replayed} <- {infile}")
    print(f"Signals stored:  {normalizer.count} -> artifacts/signals.jsonl")
    print(f"Events stored:   {analyzer.count}   -> artifacts/events.jsonl")
    print(f"Elapsed time:    {elapsed_wall:.3f} s")

    if recorded_span_s is not None:
        print(f"Recorded span:   {recorded_span_s:.3f} s")
        if elapsed_wall > 0:
            print(f"Effective rate:  {recorded_span_s / elapsed_wall:.2f}x")


if __name__ == "__main__":
    main()
