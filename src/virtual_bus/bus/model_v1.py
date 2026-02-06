from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

from .types import Signal, Event


DEFAULT_MIN_SAMPLES = 20

"""
Model V1 – Offline Signal Anomaly Detection
===========================================

This module implements the first version (V1) of the offline machine learning layer for the virtual bus pipeline.

Scope & Intent
--------------
V1 is intentionally conservative and infrastructure-focused. Its goals are:
- Validate ML plumbing without changing existing analyzer behavior
- Learn "normal" behavior strictly from clean signals.jsonl
- Produce deterministic, explainable anomaly events
- Achieve parity with rule-based detection for simple invariants (e.g. counters)
- Minimize false positives on clean data

What V1 Does
------------
- Learns robust statistics (median + MAD) over *first-differences* of signals
- Models behavior per signal name (future versions will extend this key)
- Special-cases counter-like signals using modulo increment logic
- Flags anomalies when observed deltas deviate significantly from learned norms
- Operates fully offline; does not modify analyzer.py or the main pipeline

What V1 Does NOT Do
-------------------
- Model cross-signal relationships
- Perform forecasting or temporal sequence modeling
- Learn value distributions (only deltas)
- Coalesce anomaly bursts
- Replace rule-based analysis

Assumptions
-----------
- Signals intended for ML learning must appear as repeated time-series entries
- Clean data is representative of normal system behavior
- Thresholds are intentionally high to favor precision over recall

Future Extensions (V2+)
-----------------------
- Learn per-(signal name, CAN ID) behavior
- Incorporate value-based anomaly detection
- Add burst coalescing and severity scaling
- Integrate into online two-stage analysis pipeline

This file is designed to be extended, not rewritten.
"""

def _iter_jsonl(path: Path) -> Iterator[dict]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def _write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _median(xs: List[float]) -> float:
    xs = sorted(xs)
    n = len(xs)
    if n == 0:
        return 0.0
    mid = n // 2
    if n % 2 == 1:
        return float(xs[mid])
    return 0.5 * (float(xs[mid - 1]) + float(xs[mid]))


def _mad(xs: List[float], med: float) -> float:
    # Median Absolute Deviation
    dev = [abs(x - med) for x in xs]
    return _median(dev)


@dataclass
class SignalDeltaStats:
    n: int
    median_delta: float
    mad_delta: float

    def to_dict(self) -> Dict[str, Any]:
        return {"n": self.n, "median_delta": self.median_delta, "mad_delta": self.mad_delta}

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "SignalDeltaStats":
        return SignalDeltaStats(
            n=int(d["n"]),
            median_delta=float(d["median_delta"]),
            mad_delta=float(d["mad_delta"]),
        )


@dataclass
class ModelV1:
    # Per-signal robust delta model
    per_signal: Dict[str, SignalDeltaStats]
    # For counter-like modulo behavior
    counter_mod: int = 256
    version: str = "v1-robust-delta"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "counter_mod": self.counter_mod,
            "per_signal": {k: v.to_dict() for k, v in self.per_signal.items()},
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "ModelV1":
        return ModelV1(
            per_signal={k: SignalDeltaStats.from_dict(v) for k, v in d["per_signal"].items()},
            counter_mod=int(d.get("counter_mod", 256)),
            version=str(d.get("version", "v1-robust-delta")),
        )


def train_model_from_signals(signals_jsonl: Path, *, min_samples: int = DEFAULT_MIN_SAMPLES) -> Tuple[ModelV1, Dict[str, Any]]:
    # Gather deltas per signal name
    last_by_name: Dict[str, Tuple[int, float]] = {}  # name -> (timestamp_ns, value)
    deltas: Dict[str, List[float]] = {}

    total = 0
    numeric = 0

    for row in _iter_jsonl(signals_jsonl):
        sig = Signal.from_dict(row)
        total += 1

        if sig.quality != "OK":
            continue
        if not _is_number(sig.value):
            continue

        v = float(sig.value)
        numeric += 1
        last = last_by_name.get(sig.name)
        if last is not None:
            dv = v - last[1]
            deltas.setdefault(sig.name, []).append(dv)
        last_by_name[sig.name] = (sig.timestamp_ns, v)

    per_signal: Dict[str, SignalDeltaStats] = {}
    kept = 0
    for name, ds in deltas.items():
        if len(ds) < min_samples:
            continue
        med = _median(ds)
        mad = _mad(ds, med)
        per_signal[name] = SignalDeltaStats(n=len(ds), median_delta=med, mad_delta=mad)
        kept += 1

    model = ModelV1(per_signal=per_signal)

    report = {
        "signals_total": total,
        "signals_numeric_ok": numeric,
        "signals_with_deltas": len(deltas),
        "signals_modeled": kept,
        "min_samples": min_samples,
        "note": "Model learns robust stats of first-differences (median/MAD).",
    }
    return model, report


def score_signals_to_events(
    model: ModelV1,
    signals_jsonl: Path,
    *,
    k: float = 8.0,
    min_samples: int = DEFAULT_MIN_SAMPLES,
) -> Iterator[dict]:
    # MAD -> robust sigma approx: 1.4826 * MAD (for normal-like distributions)
    last_by_name: Dict[str, float] = {}
    last_ts_by_name: Dict[str, int] = {}

    seen = 0
    flagged = 0

    for row in _iter_jsonl(signals_jsonl):
        sig = Signal.from_dict(row)
        if sig.quality != "OK":
            continue
        if not _is_number(sig.value):
            continue

        v = float(sig.value)
        name = sig.name

        last_v = last_by_name.get(name)
        last_ts = last_ts_by_name.get(name)
        last_by_name[name] = v
        last_ts_by_name[name] = sig.timestamp_ns

        if last_v is None or last_ts is None:
            continue

        seen += 1

        # Special-case counter modulo behavior if present in model stats (or just by name)
        if name == "counter":
            expected = (int(last_v) + 1) % model.counter_mod
            got = int(v) % model.counter_mod
            if got != expected:
                flagged += 1
                ev = Event(
                    timestamp_ns=sig.timestamp_ns,
                    event_type="MODEL_COUNTER_JUMP",
                    severity="WARN",
                    subject=name,
                    details={
                        "last": int(last_v),
                        "expected": expected,
                        "got": got,
                        "rule": "mod_increment",
                        "source_can_id": sig.source_can_id,
                        "source_node": sig.source_node,
                    },
                )
                yield ev.to_dict()
            continue

        stats = model.per_signal.get(name)
        if stats is None or stats.n < min_samples:
            continue

        dv = v - last_v
        med = stats.median_delta
        mad = stats.mad_delta

        # If MAD is ~0, treat as "very stable": only flag huge deviations
        robust_sigma = 1.4826 * mad
        if robust_sigma < 1e-9:
            # stable signal; only flag if dv deviates from median by a hard epsilon
            if abs(dv - med) > 1.0:  # conservative; adjust later if needed
                flagged += 1
                ev = Event(
                    timestamp_ns=sig.timestamp_ns,
                    event_type="MODEL_DELTA_OUTLIER",
                    severity="WARN",
                    subject=name,
                    details={
                        "delta": dv,
                        "median_delta": med,
                        "mad_delta": mad,
                        "score": float("inf"),
                        "threshold_k": k,
                        "note": "MAD~0; stable-signal heuristic",
                        "source_can_id": sig.source_can_id,
                        "source_node": sig.source_node,
                    },
                )
                yield ev.to_dict()
            continue

        score = abs(dv - med) / robust_sigma
        if score > k:
            flagged += 1
            ev = Event(
                timestamp_ns=sig.timestamp_ns,
                event_type="MODEL_DELTA_OUTLIER",
                severity="WARN",
                subject=name,
                details={
                    "delta": dv,
                    "median_delta": med,
                    "mad_delta": mad,
                    "robust_sigma": robust_sigma,
                    "score": score,
                    "threshold_k": k,
                    "source_can_id": sig.source_can_id,
                    "source_node": sig.source_node,
                },
            )
            yield ev.to_dict()


def save_model(model: ModelV1, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(model.to_dict(), indent=2), encoding="utf-8")


def load_model(path: Path) -> ModelV1:
    d = json.loads(path.read_text(encoding="utf-8"))
    return ModelV1.from_dict(d)
