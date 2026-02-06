from __future__ import annotations

import argparse
import json
from pathlib import Path

from virtual_bus.bus.model_v1 import (
    train_model_from_signals,
    score_signals_to_events,
    save_model,
    load_model,
)

def main() -> int:
    ap = argparse.ArgumentParser(description="Offline ML V1: train on signals.jsonl, write model_events.jsonl")
    ap.add_argument("--input", type=Path, required=True, help="Path to signals.jsonl")
    ap.add_argument("--out", type=Path, required=True, help="Path to write model_events.jsonl")
    ap.add_argument("--model", type=Path, required=True, help="Path to model artifact (json)")
    ap.add_argument("--train", action="store_true", help="Train model from --input and save to --model")
    ap.add_argument("--report", type=Path, default=None, help="Optional: write training/scoring report json")
    ap.add_argument("--k", type=float, default=8.0, help="Outlier threshold in robust-sigma units (higher = fewer FPs)")
    ap.add_argument("--min-samples", type=int, default=20, help="Min delta samples per signal to model")

    args = ap.parse_args()

    report = {}

    if args.train:
        model, train_report = train_model_from_signals(args.input, min_samples=args.min_samples)
        save_model(model, args.model)
        report["train"] = train_report
    else:
        model = load_model(args.model)

    events_iter = score_signals_to_events(
        model,
        args.input,
        k=args.k,
        min_samples=args.min_samples
    )

    # Write output
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        n = 0
        for ev in events_iter:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
            n += 1

    report["score"] = {
        "input": str(args.input),
        "out": str(args.out),
        "events_written": n,
        "k": args.k
    }

    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"wrote {n} model events -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
