from __future__ import annotations

from dataclasses import dataclass

import pytest

from virtual_bus.bus.analyzer import Analyzer
from virtual_bus.bus.types import Signal


@dataclass
class DummyWriter:
    rows: list[dict]

    def __init__(self) -> None:
        self.rows = []

    def append(self, d: dict) -> None:
        self.rows.append(d)


def _make_analyzer(tmp_path, *, watch_signals=None) -> Analyzer:
    if watch_signals is None:
        a = Analyzer(artifacts_dir=tmp_path)
    else:
        a = Analyzer(artifacts_dir=tmp_path, watch_signals=watch_signals)
    a.writer = DummyWriter()
    return a


def test_analyzer_defaults_emit_event_on_counter_jump(tmp_path) -> None:
    a = _make_analyzer(tmp_path)

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


def test_analyzer_defaults_wraparound_is_ok(tmp_path) -> None:
    a = _make_analyzer(tmp_path)

    # wrap-around: 254 -> 255 -> 0 -> 1 is valid mod-256
    a.on_signal(Signal(timestamp_ns=100, name="counter", value=254))
    a.on_signal(Signal(timestamp_ns=200, name="counter", value=255))
    a.on_signal(Signal(timestamp_ns=300, name="counter", value=0))
    a.on_signal(Signal(timestamp_ns=400, name="counter", value=1))

    assert a.count == 0
    assert a.writer.rows == []


def test_analyzer_defaults_emit_event_on_temp_spike(tmp_path) -> None:
    a = _make_analyzer(tmp_path)

    # small moves are fine
    a.on_signal(Signal(timestamp_ns=100, name="temperature_deciC", value=250))
    a.on_signal(Signal(timestamp_ns=200, name="temperature_deciC", value=251))
    assert a.count == 0

    # spike: delta +20 deciC (2.0C) > threshold (0.5C)
    a.on_signal(Signal(timestamp_ns=300, name="temperature_deciC", value=271))

    assert a.count == 1
    assert len(a.writer.rows) == 1

    ev = a.writer.rows[0]
    assert ev["event_type"] == "TEMP_SPIKE"
    assert ev["severity"] == "WARN"
    assert ev["subject"] == "temperature_deciC"
    assert ev["timestamp_ns"] == 300
    assert ev["details"]["last"] == 251
    assert ev["details"]["got"] == 271
    assert ev["details"]["delta_deciC"] == 20


def test_analyzer_defaults_emit_event_on_voltage_spike(tmp_path) -> None:
    a = _make_analyzer(tmp_path)

    a.on_signal(Signal(timestamp_ns=100, name="voltage_mv", value=12000))
    a.on_signal(Signal(timestamp_ns=200, name="voltage_mv", value=12001))
    assert a.count == 0

    # spike/sag: delta -500 mV > threshold (100 mV)
    a.on_signal(Signal(timestamp_ns=300, name="voltage_mv", value=11501))

    assert a.count == 1
    assert len(a.writer.rows) == 1

    ev = a.writer.rows[0]
    assert ev["event_type"] == "VOLTAGE_SPIKE"
    assert ev["severity"] == "WARN"
    assert ev["subject"] == "voltage_mv"
    assert ev["timestamp_ns"] == 300
    assert ev["details"]["last"] == 12001
    assert ev["details"]["got"] == 11501
    assert ev["details"]["delta_mv"] == -500


def test_analyzer_ignores_bad_quality_even_if_watched(tmp_path) -> None:
    a = _make_analyzer(tmp_path, watch_signals={"counter"})

    a.on_signal(Signal(timestamp_ns=100, name="counter", value=10, quality="UNMAPPED"))
    a.on_signal(Signal(timestamp_ns=200, name="counter", value=11, quality="DECODE_ERROR"))

    assert a.count == 0
    assert a.writer.rows == []


def test_analyzer_watch_signals_filters_events(tmp_path) -> None:
    # Only watch counter, temperature/voltage should not produce events
    a = _make_analyzer(tmp_path, watch_signals={"counter"})

    a.on_signal(Signal(timestamp_ns=100, name="temperature_deciC", value=250))
    a.on_signal(Signal(timestamp_ns=200, name="temperature_deciC", value=271))  # would be spike if watched

    a.on_signal(Signal(timestamp_ns=300, name="voltage_mv", value=12000))
    a.on_signal(Signal(timestamp_ns=400, name="voltage_mv", value=11501))       # would be spike if watched

    assert a.count == 0
    assert a.writer.rows == []
