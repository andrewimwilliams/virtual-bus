from __future__ import annotations

import json
from pathlib import Path

from virtual_bus.bus.bus import Bus
from virtual_bus.bus.types import Frame, Signal
from virtual_bus.bus.normalizer import Normalizer
from virtual_bus.bus.analyzer import Analyzer
from virtual_bus.bus.observer import Observer
from virtual_bus.bus.generator import create_traffic_generator


NOISY_TEST_ANOMALY_RATE = 0.25
TEST_SEED = 123


def _mapping_for_profile(profile: str) -> dict[int, list[tuple]]:
    if profile == "single":
        return {0x123: [("counter", 0, "count")]}
    if profile == "multi":
        return {
            0x123: [("counter", 0, "count")],
            0x124: [("temperature_deciC", "u16_le", 0, "deciC")],
            0x125: [("voltage_mv", "u16_le", 0, "mV")],
        }
    raise ValueError(f"Unknown profile: {profile}")


def _run_pipeline(
    tmp_path: Path,
    *,
    mode: str,
    profile: str = "single",
    duration_s: float = 0.25,
    period_ms: int = 5,
    seed: int | None = None,
    anomaly_rate: float = 0.0,
) -> tuple[int, int, int, Path]:
    
    artifacts_dir = tmp_path / f"{mode}_{profile}"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    frame_bus: Bus[Frame] = Bus()
    signal_bus: Bus[Signal] = Bus()

    observer = Observer(artifacts_dir)
    frame_bus.subscribe(observer.on_frame)

    analyzer = Analyzer(artifacts_dir)
    signal_bus.subscribe(analyzer.on_signal)

    mapping = _mapping_for_profile(profile)
    normalizer = Normalizer(artifacts_dir, mapping, publish_signal=signal_bus.publish)
    frame_bus.subscribe(normalizer.on_frame)

    gen = create_traffic_generator(
        scenario=mode,
        profile=profile,
        period_ms=period_ms,
        seed=seed,
        anomaly_rate=anomaly_rate,
    )
    gen.run(frame_bus.publish, duration_s=duration_s)

    normalizer.close()
    analyzer.close()
    observer.close()

    return observer.count, normalizer.count, analyzer.count, artifacts_dir


def test_clean_single_produces_no_events(tmp_path: Path) -> None:
    frames, signals, events, _ = _run_pipeline(
        tmp_path,
        mode="clean",
        profile="single",
        anomaly_rate=0.0,
        seed=TEST_SEED,
    )
    assert frames > 0
    assert signals > 0
    assert events == 0


def test_clean_multi_signals_are_ok_and_include_expected_names(tmp_path: Path) -> None:
    frames, signals, events, artifacts_dir = _run_pipeline(
        tmp_path,
        mode="clean",
        profile="multi",
        anomaly_rate=0.0,
        seed=TEST_SEED,
    )

    assert frames > 0
    assert signals > 0
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


def test_noisy_multi_produces_events(tmp_path: Path) -> None:
    frames, signals, events, _ = _run_pipeline(
        tmp_path,
        mode="noisy",
        profile="multi",
        duration_s=0.25,
        period_ms=5,
        seed=TEST_SEED,
        anomaly_rate=NOISY_TEST_ANOMALY_RATE,
    )

    assert frames > 0
    assert signals > 0
    assert events >= 1
