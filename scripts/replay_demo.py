from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from virtual_bus.bus.bus import Bus
from virtual_bus.bus.types import Frame, Signal
from virtual_bus.bus.normalizer import Normalizer
from virtual_bus.bus.analyzer import Analyzer
from virtual_bus.bus.replayer import FrameReplayer


def nice_path(path: Path, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except Exception:
        return str(path)


def load_run_meta(meta_path: Path) -> dict[str, Any]:
    if not meta_path.exists():
        raise SystemExit(
            f"Missing run metadata: {meta_path}\n"
            f"Run recordings via: python -m scripts.run_demo (which writes run_meta.json)."
        )
    return json.loads(meta_path.read_text(encoding="utf-8"))


def decode_mapping(raw: Any) -> dict[int, list[tuple]]:
    if not isinstance(raw, dict):
        raise SystemExit("Invalid run_meta.json: 'mapping' must be a dict")

    mapping: dict[int, list[tuple]] = {}
    for k, v in raw.items():
        try:
            can_id = int(k) if not isinstance(k, int) else k
        except Exception as e:
            raise SystemExit(f"Invalid mapping key in run_meta.json: {k!r} ({e})")

        if not isinstance(v, list):
            raise SystemExit(f"Invalid mapping value for CAN ID {k!r}: expected list")

        mapping[can_id] = [tuple(item) for item in v]
    return mapping


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay a recorded frames.jsonl through the pipeline.")
    parser.add_argument(
        "--infile",
        type=Path,
        required=True,
        help="Path to frames.jsonl to replay (required).",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=None,
        help="Optional output directory for signals/events (default: infile's parent).",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max frames to replay.")
    parser.add_argument("--speed", type=float, default=1.0, help="Playback speed factor (relative timing only).")
    parser.add_argument(
        "--timing",
        choices=("none", "relative"),
        default="relative",
        help="Replay timing mode: 'relative' sleeps based on timestamps; 'none' runs as fast as possible.",
    )
    args = parser.parse_args()

    start = time.perf_counter()

    root = Path(__file__).resolve().parents[1]
    infile = args.infile

    if not infile.exists():
        raise SystemExit(f"Input file not found: {infile}")

    # Output directory defaults to where the input lives
    outdir = args.outdir if args.outdir is not None else infile.parent
    outdir.mkdir(parents=True, exist_ok=True)

    # Load metadata produced by run_demo
    meta_path = infile.parent / "run_meta.json"
    meta = load_run_meta(meta_path)

    mode = meta.get("mode", "unknown")
    profile = meta.get("profile", "unknown")
    seed = meta.get("seed", None)
    anomaly_rate = meta.get("anomaly_rate", 0.0)
    mapping = decode_mapping(meta.get("mapping"))

    frame_bus: Bus[Frame] = Bus()
    signal_bus: Bus[Signal] = Bus()

    analyzer = Analyzer(outdir)
    signal_bus.subscribe(analyzer.on_signal)

    normalizer = Normalizer(outdir, mapping, publish_signal=signal_bus.publish)
    frame_bus.subscribe(normalizer.on_frame)

    replayer = FrameReplayer(
        infile,
        timing=args.timing,
        speed=args.speed,
    )

    replayed = replayer.run(frame_bus.publish, limit=args.limit)
    elapsed = time.perf_counter() - start

    normalizer.close()
    analyzer.close()

    frames_path = infile
    signals_path = outdir / "signals.jsonl"
    events_path = outdir / "events.jsonl"

    print("=== Demo complete ===")
    print(f"Mode:             {mode}")
    print(f"Anomaly rate:     {anomaly_rate}")
    print(f"Profile:          {profile}")
    print(f"Seed:             {seed}")
    print(f"Frames sent:      {replayed}")
    print(f"Frames stored:    {replayed:<4} -> {nice_path(frames_path, root)}")
    print(f"Signals stored:   {normalizer.count:<4} -> {nice_path(signals_path, root)}")
    print(f"Events stored:    {analyzer.count:<4} -> {nice_path(events_path, root)}")
    print(f"Elapsed time:     {elapsed:.3f} s")


if __name__ == "__main__":
    main()
