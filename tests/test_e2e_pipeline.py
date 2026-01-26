from __future__ import annotations

import json
from pathlib import Path

from virtual_bus.bus.bus import Bus
from virtual_bus.bus.types import Frame, Signal
from virtual_bus.bus.replayer import FrameReplayer
from virtual_bus.bus.normalizer import Normalizer
from virtual_bus.bus.analyzer import Analyzer


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _run_pipeline(frames_path: Path, artifacts_dir: Path, *, speed: float) -> dict:

    # Runs: FrameReplayer -> Frame Bus -> Normalizer -> Signal Bus -> Analyzer
    # Returns basic counts + paths

    frame_bus: Bus[Frame] = Bus()
    signal_bus: Bus[Signal] = Bus()

    analyzer = Analyzer(artifacts_dir, watch_signal="counter")
    signal_bus.subscribe(analyzer.on_signal)

    mapping = {0x123: [("counter", 0, "count")]}
    normalizer = Normalizer(artifacts_dir, mapping, publish_signal=signal_bus.publish)
    frame_bus.subscribe(normalizer.on_frame)

    replayer = FrameReplayer(frames_path, timing="none", speed=speed)
    replayed = replayer.run(frame_bus.publish)

    return {
        "frames_replayed": replayed,
        "signals_written": normalizer.count,
        "events_written": analyzer.count,
        "signals_path": artifacts_dir / "signals.jsonl",
        "events_path": artifacts_dir / "events.jsonl",
    }


def test_e2e_pipeline_matches_golden_events(tmp_path: Path) -> None:
    root = _repo_root()
    frames_in = root / "tests" / "fixtures" / "frames.jsonl"
    golden_signals = root / "tests" / "fixtures" / "signals.jsonl"
    golden_events = root / "tests" / "fixtures" / "events.jsonl"

    result = _run_pipeline(frames_in, tmp_path, speed=1.0)

    produced_events = _read_jsonl(result["events_path"])
    expected_events = _read_jsonl(golden_events)
    assert produced_events == expected_events

    produced_signals = _read_jsonl(result["signals_path"])
    expected_signals = _read_jsonl(golden_signals)
    assert produced_signals == expected_signals

    assert len(produced_events) == 1
    ev = produced_events[0]

    assert ev["event_type"] == "COUNTER_JUMP"
    assert ev["severity"] == "WARN"
    assert ev["subject"] == "counter"

    details = ev["details"]
    assert set(details.keys()) >= {"last", "expected", "got"}
    assert isinstance(details["last"], int)
    assert isinstance(details["expected"], int)
    assert isinstance(details["got"], int)



def test_e2e_pipeline_events_independent_of_speed(tmp_path: Path) -> None:

    # Speed should only affect sleeping behavior
    # With timing='none' it must not affect logical outputs

    root = _repo_root()
    frames_in = root / "tests" / "fixtures" / "frames.jsonl"

    r1 = _run_pipeline(frames_in, tmp_path / "run1", speed=1.0)
    r2 = _run_pipeline(frames_in, tmp_path / "run2", speed=50.0)

    e1 = _read_jsonl(r1["events_path"])
    e2 = _read_jsonl(r2["events_path"])

    assert e1 == e2
