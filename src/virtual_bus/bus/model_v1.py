from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

from .types import Signal, Event


DEFAULT_MIN_SAMPLES = 20

_MIN_DEV_BY_NAME = {
    "temperature_deciC": 5.0,
    "voltage_mv": 100.0,
}

"""
Model V1 – Offline Signal Anomaly Detection
===========================================

V1 implements a conservative, offline ML layer for the virtual bus pipeline.
Its primary purpose is to validate ML plumbing and event semantics without
changing or replacing the existing rule-based analyzer.

Design Goals
------------
- Learn "normal" behavior exclusively from clean signals.jsonl
- Produce deterministic, explainable anomaly events
- Match analyzer behavior for simple invariants (e.g., counters, spike rules)
- Minimize false positives on clean data

Approach
--------
- Learn robust statistics (median + MAD) over first-differences (deltas)
- Model behavior per (source CAN ID, signal name)
- Special-case counters using modulo increment rules
- Mirror analyzer spike thresholds when appropriate
- Operate fully offline; no impact to the main pipeline

Non-Goals
---------
- Forecasting or temporal modeling
- Cross-signal correlation
- Online inference or replacement of analyzer logic

Future Work (V2+)
-----------------
- Value-based anomaly detection
- Burst coalescing and severity scaling
- Integration into a two-stage (rules + ML) pipeline
"""

def _model_key(sig: Signal) -> str:
    # Keyed per CAN ID and signal name so multiple streams don't collide
    # Keep string for JSON-serializable dict keys
    return f"{sig.source_can_id}:{sig.name}"

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


def _percentile(xs: List[float], p: float) -> float:
    # p in [0, 100]
    if not xs:
        return 0.0
    xs = sorted(xs)
    if p <= 0:
        return float(xs[0])
    if p >= 100:
        return float(xs[-1])
    k = (len(xs) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(xs[int(k)])
    d0 = float(xs[f]) * (c - k)
    d1 = float(xs[c]) * (k - f)
    return d0 + d1


@dataclass
class SignalDeltaStats:
    n: int
    median_delta: float
    mad_delta: float
    abs_dev_p99: float  # Fallback tolerance when MAD==0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n": self.n,
            "median_delta": self.median_delta,
            "mad_delta": self.mad_delta,
            "abs_dev_p99": self.abs_dev_p99,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "SignalDeltaStats":
        return SignalDeltaStats(
            n=int(d["n"]),
            median_delta=float(d["median_delta"]),
            mad_delta=float(d["mad_delta"]),
            abs_dev_p99=float(d.get("abs_dev_p99", 0.0)),
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
    # Gather deltas per (source CAN ID, signal name)
    last_by_key: Dict[str, Tuple[int, float]] = {}  # name -> (timestamp_ns, value)
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
        key = _model_key(sig)
        last = last_by_key.get(key)
        if last is not None:
            dv = v - last[1]
            deltas.setdefault(key, []).append(dv)
        last_by_key[key] = (sig.timestamp_ns, v)

    per_signal: Dict[str, SignalDeltaStats] = {}
    kept = 0
    for key, ds in deltas.items():
        if len(ds) < min_samples:
            continue
        med = _median(ds)
        mad = _mad(ds, med)
        abs_dev = [abs(d - med) for d in ds]
        abs_dev_p99 = _percentile(abs_dev, 99.0)
        per_signal[key] = SignalDeltaStats(
            n=len(ds),
            median_delta=med,
            mad_delta=mad,
            abs_dev_p99=abs_dev_p99,
        )
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
    last_by_key: Dict[str, float] = {}
    last_ts_by_key: Dict[str, int] = {}

    for row in _iter_jsonl(signals_jsonl):
        sig = Signal.from_dict(row)
        if sig.quality != "OK":
            continue
        if not _is_number(sig.value):
            continue

        v = float(sig.value)
        name = sig.name
        key = _model_key(sig)

        last_v = last_by_key.get(key)
        last_ts = last_ts_by_key.get(key)
        last_by_key[key] = v
        last_ts_by_key[key] = sig.timestamp_ns

        if last_v is None or last_ts is None:
            continue

        # Special-case counter modulo behavior
        if name == "counter":
            expected = (int(last_v) + 1) % model.counter_mod
            got = int(v) % model.counter_mod
            if got != expected:
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
                        "model_key": key,
                        "source_can_id": sig.source_can_id,
                        "source_node": sig.source_node,
                    },
                )
                yield ev.to_dict()
            continue

        stats = model.per_signal.get(key)
        if stats is None or stats.n < min_samples:
            continue

        dv = v - last_v
        med = stats.median_delta
        mad = stats.mad_delta

        robust_sigma = 1.4826 * mad
        if robust_sigma < 1e-9:
            # MAD==0: stable in clean. If this signal has an explicit analyzer-style spike rule,
            # mirror it exactly: abs(dv) > threshold (strict >).
            rule_thresh = _MIN_DEV_BY_NAME.get(name)
            if rule_thresh is not None:
                if abs(dv) > rule_thresh:
                    ev = Event(
                        timestamp_ns=sig.timestamp_ns,
                        event_type="MODEL_DELTA_OUTLIER",
                        severity="WARN",
                        subject=name,
                        details={
                            "delta": dv,
                            "rule_threshold": rule_thresh,
                            "note": "MAD==0; analyzer parity (abs(delta) > threshold)",
                            "model_key": key,
                            "source_can_id": sig.source_can_id,
                            "source_node": sig.source_node,
                        },
                    )
                    yield ev.to_dict()
                continue

            # Otherwise: ML fallback using learned tolerance from clean run
            tol = stats.abs_dev_p99
            margin = 0.0 if tol >= 1.0 else 1.0
            if abs(dv - med) > (tol + margin):
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
                        "note": "MAD==0; p99 abs-dev fallback",
                        "abs_dev_p99": tol,
                        "threshold": tol + margin,
                        "model_key": key,
                        "source_can_id": sig.source_can_id,
                        "source_node": sig.source_node,
                    },
                )
                yield ev.to_dict()
            continue

        # Normal robust-z scoring path when MAD > 0
        score = abs(dv - med) / robust_sigma
        if score > k:
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
                    "model_key": key,
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
