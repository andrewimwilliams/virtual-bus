from __future__ import annotations

from pathlib import Path
import json

from virtual_bus.bus.bus import Bus
from virtual_bus.bus.types import Frame, Signal
from virtual_bus.bus.normalizer import Normalizer
from virtual_bus.bus.analyzer import Analyzer
from virtual_bus.bus.observer import Observer
from virtual_bus.bus.generator import create_traffic_generator


def _run_pipeline(
    tmp_path: Path,
    *,
    mode: str,
    profile: str = "single",
    duration_s: float = 0.25,
    period_ms: int = 1,
    seed: int | None = None,
    p_counter_jump: float = 0.0,
) -> tuple[int, int, int, Path]:

    # Returns: (frames_written, signals_written, events_written, artifacts_dir)

    artifacts_dir = tmp_path / f"{mode}_{profile}"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    frame_bus: Bus[Frame] = Bus()
    signal_bus: Bus[Signal] = Bus()

    observer = Observer(artifacts_dir)
    frame_bus.subscribe(observer.on_frame)

    analyzer = Analyzer(artifacts_dir, watch_signal="counter")
    signal_bus.subscribe(analyzer.on_signal)

    # Mapping that matches Normalizer + generator:
    # - counter is byte 0
    # - temperature and voltage are u16 little-endian at offset 0
    if profile == "single":
        mapping = {0x123: [("counter", 0, "count")]}
    else:
        mapping = {
            0x123: [("counter", 0, "count")],
            0x124: [("temperature_deciC", "u16_le", 0, "deciC")],
            0x125: [("voltage_mv", "u16_le", 0, "mV")],
        }

    normalizer = Normalizer(artifacts_dir, mapping, publish_signal=signal_bus.publish)
    frame_bus.subscribe(normalizer.on_frame)

    gen = create_traffic_generator(
        scenario=mode,
        profile=profile,          # "single" or "multi"
        period_ms=period_ms,      # fast tests
        seed=seed,                # deterministic when needed
        p_counter_jump=p_counter_jump,
    )
    gen.run(frame_bus.publish, duration_s=duration_s)

    normalizer.close()
    analyzer.close()
    observer.close()

    return observer.count, normalizer.count, analyzer.count, artifacts_dir


def test_clean_run_produces_no_events(tmp_path: Path) -> None:
    frames, signals, events, _ = _run_pipeline(
        tmp_path,
        mode="clean",
        profile="single",
        p_counter_jump=0.0,
    )
    assert frames > 0
    assert signals > 0
    assert events == 0


def test_clean_multi_signals_match_frames_and_are_ok(tmp_path: Path) -> None:
    frames, signals, events, artifacts_dir = _run_pipeline(
        tmp_path,
        mode="clean",
        profile="multi",
        p_counter_jump=0.0,
    )

    assert frames > 0
    assert signals == frames
    assert events == 0

    signals_path = artifacts_dir / "signals.jsonl"
    names: set[str] = set()
    qualities: set[str] = set()

    for line in signals_path.read_text(encoding="utf-8").splitlines():
        d = json.loads(line)
        names.add(d.get("name"))
        qualities.add(d.get("quality"))

    assert qualities == {"OK"}
    assert {"counter", "temperature_deciC", "voltage_mv"} <= names


def test_noisy_run_produces_events(tmp_path: Path) -> None:
    # Deterministic and non-flaky:
    # - multi profile means only ~1/3 frames are counter frames
    # - higher p and fixed seed so events are almost guaranteed
    frames, signals, events, _ = _run_pipeline(
        tmp_path,
        mode="noisy",
        profile="multi",
        duration_s=0.25,
        seed=123,
        p_counter_jump=0.25,
    )
    assert frames > 0
    assert signals == frames
    assert events >= 1
