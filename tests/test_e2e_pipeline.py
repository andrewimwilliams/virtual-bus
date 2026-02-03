from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from virtual_bus.bus.bus import Bus
from virtual_bus.bus.types import Frame, Signal
from virtual_bus.bus.replayer import FrameReplayer
from virtual_bus.bus.normalizer import Normalizer
from virtual_bus.bus.analyzer import Analyzer


NOISY_FIXTURE_ANOMALY_RATE = 0.25
TEST_SEED = 123


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _write_run_meta(meta_path: Path, *, mode: str, profile: str, anomaly_rate: float, seed: int | None, mapping: dict[int, list[tuple]]) -> None:
    meta: dict[str, Any] = {
        "schema_version": 1,
        "tool": "test",
        "mode": mode,
        "profile": profile,
        "seed": seed,
        "anomaly_rate": anomaly_rate,
        "mapping": mapping,
    }
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")


def _load_run_meta(meta_path: Path) -> dict:
    return json.loads(meta_path.read_text(encoding="utf-8"))


def _decode_mapping(raw: Any) -> dict[int, list[tuple]]:
    if not isinstance(raw, dict):
        raise TypeError("mapping must be a dict")

    mapping: dict[int, list[tuple]] = {}
    for k, v in raw.items():
        can_id = int(k)
        if not isinstance(v, list):
            raise TypeError(f"mapping[{k!r}] must be a list")
        mapping[can_id] = [tuple(item) for item in v]
    return mapping


def _prepare_recording_dir(tmp_path: Path, *, fixture_frames: Path, mode: str, anomaly_rate: float) -> tuple[Path, Path]:
    recording_dir = tmp_path / "recording"
    recording_dir.mkdir(parents=True, exist_ok=True)

    frames_path = recording_dir / "frames.jsonl"
    frames_path.write_text(fixture_frames.read_text(encoding="utf-8"), encoding="utf-8")

    meta_path = recording_dir / "run_meta.json"

    # Single-profile mapping (counter only)
    mapping = {0x123: [("counter", 0, "count")]}

    _write_run_meta(
        meta_path,
        mode=mode,
        profile="single",
        anomaly_rate=anomaly_rate,
        seed=TEST_SEED,
        mapping=mapping,
    )

    return frames_path, meta_path


def _run_pipeline(frames_path: Path, meta_path: Path, outdir: Path, *, speed: float) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)

    frame_bus: Bus[Frame] = Bus()
    signal_bus: Bus[Signal] = Bus()

    analyzer = Analyzer(outdir)
    signal_bus.subscribe(analyzer.on_signal)

    meta = _load_run_meta(meta_path)
    assert meta["schema_version"] == 1
    assert meta["profile"] == "single"

    mapping = _decode_mapping(meta["mapping"])

    normalizer = Normalizer(outdir, mapping, publish_signal=signal_bus.publish)
    frame_bus.subscribe(normalizer.on_frame)

    replayer = FrameReplayer(frames_path, timing="none", speed=speed)
    replayed = replayer.run(frame_bus.publish)

    normalizer.close()
    analyzer.close()

    return {
        "frames_replayed": replayed,
        "signals_written": normalizer.count,
        "events_written": analyzer.count,
        "signals_path": outdir / "signals.jsonl",
        "events_path": outdir / "events.jsonl",
    }


def test_e2e_single_noisy_replay_matches_golden(tmp_path: Path) -> None:
    root = _repo_root()

    fixture_frames = root / "tests" / "fixtures" / "single_noisy_frames.jsonl"
    golden_signals = root / "tests" / "fixtures" / "single_noisy_signals.jsonl"
    golden_events = root / "tests" / "fixtures" / "single_noisy_events.jsonl"

    frames_path, meta_path = _prepare_recording_dir(
        tmp_path,
        fixture_frames=fixture_frames,
        mode="noisy",
        anomaly_rate=NOISY_FIXTURE_ANOMALY_RATE,
    )

    result = _run_pipeline(frames_path, meta_path, tmp_path / "out", speed=1.0)

    produced_events = _read_jsonl(result["events_path"])
    expected_events = _read_jsonl(golden_events)
    assert produced_events == expected_events

    produced_signals = _read_jsonl(result["signals_path"])
    expected_signals = _read_jsonl(golden_signals)
    assert produced_signals == expected_signals

    assert len(produced_events) >= 1
    ev = produced_events[0]
    assert ev["event_type"] == "COUNTER_JUMP"
    assert ev["severity"] in {"WARN", "ERROR"}
    assert ev["subject"] == "counter"


def test_e2e_single_clean_replay_matches_golden(tmp_path: Path) -> None:
    root = _repo_root()

    fixture_frames = root / "tests" / "fixtures" / "single_clean_frames.jsonl"
    golden_signals = root / "tests" / "fixtures" / "single_clean_signals.jsonl"
    golden_events = root / "tests" / "fixtures" / "single_clean_events.jsonl"

    frames_path, meta_path = _prepare_recording_dir(
        tmp_path,
        fixture_frames=fixture_frames,
        mode="clean",
        anomaly_rate=0.0,
    )

    result = _run_pipeline(frames_path, meta_path, tmp_path / "out", speed=1.0)

    produced_events = _read_jsonl(result["events_path"])
    expected_events = _read_jsonl(golden_events)
    assert produced_events == expected_events
    assert len(produced_events) == 0

    produced_signals = _read_jsonl(result["signals_path"])
    expected_signals = _read_jsonl(golden_signals)
    assert produced_signals == expected_signals


def test_e2e_events_independent_of_speed(tmp_path: Path) -> None:
    root = _repo_root()

    fixture_frames = root / "tests" / "fixtures" / "single_noisy_frames.jsonl"
    frames_path, meta_path = _prepare_recording_dir(
        tmp_path,
        fixture_frames=fixture_frames,
        mode="noisy",
        anomaly_rate=NOISY_FIXTURE_ANOMALY_RATE,
    )

    r1 = _run_pipeline(frames_path, meta_path, tmp_path / "run1", speed=1.0)
    r2 = _run_pipeline(frames_path, meta_path, tmp_path / "run2", speed=50.0)

    s1 = _read_jsonl(r1["signals_path"])
    s2 = _read_jsonl(r2["signals_path"])
    assert s1 == s2

    e1 = _read_jsonl(r1["events_path"])
    e2 = _read_jsonl(r2["events_path"])
    assert e1 == e2
