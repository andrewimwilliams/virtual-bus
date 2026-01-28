from __future__ import annotations

from pathlib import Path
import json

from virtual_bus.bus.bus import Bus
from virtual_bus.bus.types import Frame, Signal
from virtual_bus.bus.normalizer import Normalizer
from virtual_bus.bus.analyzer import Analyzer
from virtual_bus.bus.observer import Observer
from virtual_bus.bus.generator import create_traffic_generator


def _run_pipeline(tmp_path: Path, *, mode: str, duration_s: float = 0.5) -> tuple[int, int, int, Path]:

    # Returns: (frames_written, signals_written, events_written, artifacts_dir)
    
    artifacts_dir = tmp_path / mode
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    frame_bus: Bus[Frame] = Bus()
    signal_bus: Bus[Signal] = Bus()

    observer = Observer(artifacts_dir)
    frame_bus.subscribe(observer.on_frame)

    analyzer = Analyzer(artifacts_dir, watch_signal="counter")
    signal_bus.subscribe(analyzer.on_signal)

    mapping = {0x123: [("counter", 0, "count")]}
    normalizer = Normalizer(artifacts_dir, mapping, publish_signal=signal_bus.publish)
    frame_bus.subscribe(normalizer.on_frame)

    gen = create_traffic_generator(scenario=mode, can_id=0x123, period_ms=1)  # fast tests
    gen.run(frame_bus.publish, duration_s=duration_s)

    normalizer.close()
    analyzer.close()
    observer.close()

    return observer.count, normalizer.count, analyzer.count, artifacts_dir


def test_clean_run_produces_no_events(tmp_path: Path) -> None:
    frames, signals, events, _ = _run_pipeline(tmp_path, mode="clean")
    assert frames > 0
    assert signals > 0
    assert events == 0


def test_noisy_run_produces_events(tmp_path: Path) -> None:
    # Ensure default is hit: fault_at (80)
    frames, signals, events, _ = _run_pipeline(tmp_path, mode="noisy", duration_s=0.2)
    assert frames > 0
    assert signals > 0
    assert events >= 1


def test_clean_run_signals_all_ok(tmp_path: Path) -> None:
    _, _, _, artifacts_dir = _run_pipeline(tmp_path, mode="clean")
    signals_path = artifacts_dir / "signals.jsonl"
    qualities = []
    for line in signals_path.read_text(encoding="utf-8").splitlines():
        d = json.loads(line)
        qualities.append(d.get("quality"))

    assert qualities, "Expected at least one signal"
    assert set(qualities) == {"OK"}
