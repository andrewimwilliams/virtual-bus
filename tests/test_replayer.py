import json
from pathlib import Path

import pytest

from virtual_bus.bus.replayer import FrameReplayer
from virtual_bus.bus.types import Frame


def _write_frames_jsonl(path: Path, frames: list[Frame]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for fr in frames:
            f.write(json.dumps(fr.to_dict()) + "\n")


def test_replayer_reads_frames_and_calls_publish_in_order(tmp_path: Path) -> None:
    frames_path = tmp_path / "frames.jsonl"
    frames = [
        Frame(timestamp_ns=100, can_id=0x123, data=b"\x01\x02"),
        Frame(timestamp_ns=200, can_id=0x123, data=b"\x03\x04"),
        Frame(timestamp_ns=300, can_id=0x456, data=b"\xAA"),
    ]
    _write_frames_jsonl(frames_path, frames)

    seen: list[Frame] = []
    rep = FrameReplayer(path=frames_path, timing="none")
    count = rep.run(publish=seen.append)

    assert count == 3
    assert seen == frames


def test_replayer_respects_limit(tmp_path: Path) -> None:
    frames_path = tmp_path / "frames.jsonl"
    frames = [
        Frame(timestamp_ns=0, can_id=0x1, data=b"\x00"),
        Frame(timestamp_ns=1, can_id=0x1, data=b"\x01"),
        Frame(timestamp_ns=2, can_id=0x1, data=b"\x02"),
    ]
    _write_frames_jsonl(frames_path, frames)

    seen: list[Frame] = []
    rep = FrameReplayer(path=frames_path, timing="none")
    count = rep.run(publish=seen.append, limit=2)

    assert count == 2
    assert seen == frames[:2]


def test_replayer_speed_must_be_positive(tmp_path: Path) -> None:
    frames_path = tmp_path / "frames.jsonl"
    _write_frames_jsonl(frames_path, [Frame(timestamp_ns=0, can_id=0x1, data=b"\x00")])

    rep = FrameReplayer(path=frames_path, timing="none", speed=0.0)
    with pytest.raises(ValueError):
        rep.run(publish=lambda _fr: None)


def test_timing_none_never_sleeps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    frames_path = tmp_path / "frames.jsonl"
    _write_frames_jsonl(
        frames_path,
        [
            Frame(timestamp_ns=0, can_id=0x1, data=b"\x00"),
            Frame(timestamp_ns=1_000_000_000, can_id=0x1, data=b"\x01"),
        ],
    )

    def _boom(_s: float) -> None:
        raise AssertionError("time.sleep should not be called when timing='none'")

    monkeypatch.setattr("virtual_bus.bus.replayer.time.sleep", _boom)

    rep = FrameReplayer(path=frames_path, timing="none")
    rep.run(publish=lambda _fr: None)


def test_timing_relative_sleeps_scaled_and_capped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Verifies:
    #   sleep_s = (dt_ns / 1e9) / speed
    #   and sleep is capped by max_sleep_s
    frames_path = tmp_path / "frames.jsonl"
    _write_frames_jsonl(
        frames_path,
        [
            Frame(timestamp_ns=0, can_id=0x1, data=b"\x00"),
            Frame(timestamp_ns=1_000_000_000, can_id=0x1, data=b"\x01"),   # dt = 1.0s
            Frame(timestamp_ns=3_000_000_000, can_id=0x1, data=b"\x02"),   # dt = 2.0s
        ],
    )

    sleeps: list[float] = []

    def _fake_sleep(s: float) -> None:
        sleeps.append(s)

    monkeypatch.setattr("virtual_bus.bus.replayer.time.sleep", _fake_sleep)

    rep = FrameReplayer(
        path=frames_path,
        timing="relative",
        speed=2.0,         # halves dt
        max_sleep_s=0.25,  # cap
    )
    rep.run(publish=lambda _fr: None)

    # There should be two sleep calls (between frames 0->1 and 1->2)
    assert len(sleeps) == 2

    # dt=1.0s => /speed=2 => 0.5s capped to 0.25
    assert sleeps[0] == pytest.approx(0.25)
    # dt=2.0s => /speed=2 => 1.0s capped to 0.25
    assert sleeps[1] == pytest.approx(0.25)
