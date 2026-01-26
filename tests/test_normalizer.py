from __future__ import annotations

from pathlib import Path

from virtual_bus.bus.normalizer import Normalizer
from virtual_bus.bus.types import Frame, Signal


def test_normalizer_emits_mapped_signal_and_value(tmp_path: Path) -> None:
    published: list[Signal] = []

    mapping = {0x123: [("counter", 0, "count")]}
    n = Normalizer(
        artifacts_dir=tmp_path,
        mapping=mapping,
        publish_signal=published.append,
    )

    fr = Frame(timestamp_ns=100, can_id=0x123, data=b"\x2A")  # 42
    n.on_frame(fr)

    assert n.count == 1
    assert len(published) == 1

    sig = published[0]
    assert sig.timestamp_ns == 100
    assert sig.name == "counter"
    assert sig.value == 42
    assert sig.units == "count"
    assert sig.source_can_id == 0x123
    # These are optional in Frame defaults, may be None
    assert sig.source_channel == fr.channel
    assert sig.source_node == fr.source_node
    assert sig.quality == "OK"


def test_normalizer_emits_unmapped_signal_when_id_unknown(tmp_path: Path) -> None:
    published: list[Signal] = []

    n = Normalizer(
        artifacts_dir=tmp_path,
        mapping={},  # nothing mapped
        publish_signal=published.append,
    )

    fr = Frame(timestamp_ns=999, can_id=0x700, data=b"\x01\x02")
    n.on_frame(fr)

    assert n.count == 1
    sig = published[0]
    assert sig.name == "UNMAPPED"
    assert sig.value == 0
    assert sig.units is None
    assert sig.quality == "UNMAPPED"
    assert sig.source_can_id == 0x700


def test_normalizer_emits_decode_error_when_byte_index_out_of_range(tmp_path: Path) -> None:
    published: list[Signal] = []

    mapping = {0x123: [("counter", 5, "count")]}  # asks for byte 5
    n = Normalizer(
        artifacts_dir=tmp_path,
        mapping=mapping,
        publish_signal=published.append,
    )

    fr = Frame(timestamp_ns=123, can_id=0x123, data=b"\x10\x11")  # len=2
    n.on_frame(fr)

    assert n.count == 1
    sig = published[0]
    assert sig.name == "counter"
    assert sig.value == 0
    assert sig.units == "count"
    assert sig.quality == "DECODE_ERROR"
    assert sig.meta is not None
    assert sig.meta["reason"] == "byte_index_out_of_range"
    assert sig.meta["idx"] == 5
    assert sig.meta["len"] == 2


def test_normalizer_emits_multiple_signals_for_one_frame(tmp_path: Path) -> None:
    published: list[Signal] = []

    mapping = {0x123: [("a", 0, "u"), ("b", 1, "u")]}
    n = Normalizer(tmp_path, mapping, published.append)

    fr = Frame(timestamp_ns=1, can_id=0x123, data=b"\x05\x06")
    n.on_frame(fr)

    assert n.count == 2
    assert [s.name for s in published] == ["a", "b"]
    assert [s.value for s in published] == [5, 6]
