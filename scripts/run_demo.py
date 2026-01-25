from __future__ import annotations

from pathlib import Path

from virtual_bus.bus.inprocess import InProcessBus
from virtual_bus.bus.observer import Observer
from virtual_bus.bus.generator import TrafficGenerator
from virtual_bus.bus.normalizer import Normalizer
from virtual_bus.bus.analyzer import Analyzer


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    artifacts_dir = root / "artifacts"

    bus = InProcessBus()

    # Raw frame store
    observer = Observer(artifacts_dir)
    bus.subscribe(observer.on_frame)

    # Normalizer -> produces signals.jsonl
    mapping = {
        0x123: [("counter", 0, "count")],  # can_id 0x123, byte0 -> "counter"
    }
    normalizer = Normalizer(artifacts_dir, mapping)
    bus.subscribe(normalizer.on_frame)

    # Analyzer consumes signals, so call analyzer from normalizer output path
    # Inline patch by wrapping normalizer.on_frame.
    analyzer = Analyzer(artifacts_dir, watch_signal="counter")

    # Minimal slice replacing bus subscription for normalizer that calls analyzer
    bus = InProcessBus()
    bus.subscribe(observer.on_frame)

    def normalize_and_analyze(frame):
        # Call normalizer and directly feed analyzer with the produced signals by re-decoding
        normalizer.on_frame(frame)

        # Re-decode just seen signal (minimal)
        if frame.can_id == 0x123 and len(frame.data) >= 1:
            from virtual_bus.bus.types import Signal
            sig = Signal(
                timestamp_ns=frame.timestamp_ns,
                name="counter",
                value=int(frame.data[0]),
                units="count",
                source_can_id=frame.can_id,
                source_channel=frame.channel,
                source_node=frame.source_node,
            )
            analyzer.on_signal(sig)

    bus.subscribe(normalize_and_analyze)

    gen = TrafficGenerator(can_id=0x123, period_ms=20, fault_at=80)
    sent = gen.run(bus.publish, duration_s=2.5)

    print("=== Demo complete ===")
    print(f"Frames sent:    {sent}")
    print(f"Frames stored:  {observer.count}  -> artifacts/frames.jsonl")
    print(f"Signals stored: {normalizer.count} -> artifacts/signals.jsonl")
    print(f"Events stored:  {analyzer.count}   -> artifacts/events.jsonl")


if __name__ == "__main__":
    main()
