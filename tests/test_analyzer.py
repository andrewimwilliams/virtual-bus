import pytest

from virtual_bus.bus.analyzer import Analyzer
from virtual_bus.bus.types import Signal


class DummyWriter:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def append(self, d: dict) -> None:
        self.rows.append(d)


def test_analyzer_emits_event_on_counter_jump(tmp_path) -> None:
    a = Analyzer(artifacts_dir=tmp_path, watch_signal="counter")
    a.writer = DummyWriter()  # replace JsonlWriter to keep test pure/in-memory

    # normal increments: 10 -> 11 -> 12
    a.on_signal(Signal(timestamp_ns=100, name="counter", value=10))
    a.on_signal(Signal(timestamp_ns=200, name="counter", value=11))
    a.on_signal(Signal(timestamp_ns=300, name="counter", value=12))
    assert a.count == 0
    assert a.writer.rows == []

    # jump: expected 13, got 99
    a.on_signal(Signal(timestamp_ns=400, name="counter", value=99))

    assert a.count == 1
    assert len(a.writer.rows) == 1

    ev = a.writer.rows[0]
    assert ev["event_type"] == "COUNTER_JUMP"
    assert ev["severity"] == "WARN"
    assert ev["subject"] == "counter"
    assert ev["timestamp_ns"] == 400
    assert ev["details"]["last"] == 12
    assert ev["details"]["expected"] == 13
    assert ev["details"]["got"] == 99


def test_analyzer_wraparound_is_ok(tmp_path) -> None:
    a = Analyzer(artifacts_dir=tmp_path, watch_signal="counter")
    a.writer = DummyWriter()

    # wrap-around: 254 -> 255 -> 0 -> 1 is valid mod-256``
    a.on_signal(Signal(timestamp_ns=100, name="counter", value=254))
    a.on_signal(Signal(timestamp_ns=200, name="counter", value=255))
    a.on_signal(Signal(timestamp_ns=300, name="counter", value=0))
    a.on_signal(Signal(timestamp_ns=400, name="counter", value=1))

    assert a.count == 0
    assert a.writer.rows == []


def test_analyzer_ignores_wrong_signal_or_bad_quality(tmp_path) -> None:
    a = Analyzer(artifacts_dir=tmp_path, watch_signal="counter")
    a.writer = DummyWriter()

    a.on_signal(Signal(timestamp_ns=100, name="other", value=1))
    a.on_signal(Signal(timestamp_ns=200, name="counter", value=10, quality="UNMAPPED"))
    a.on_signal(Signal(timestamp_ns=300, name="counter", value=11, quality="DECODE_ERROR"))

    assert a.count == 0
    assert a.writer.rows == []
