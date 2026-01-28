from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Optional, Protocol, Literal, List

from .types import Frame


# Clock abstraction
class Clock(Protocol):
    def time_ns(self) -> int: ...
    def sleep(self, seconds: float) -> None: ...
    
@dataclass
class RealClock:
    def time_ns(self) -> int:
        return time.time_ns()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


# Anomaly injection primitives
class Anomaly(Protocol):
    def apply(self, *, frame_index: int, counter: int, payload: bytearray) -> int:
            ""
            # Optionally modify counter/payload
            # Return the counter value to use for this frame

    
@dataclass(frozen=True)
class CounterJumpAtFrame:
    at_frame: int
    delta: int = 50

    def apply(self, *, frame_index: int, counter: int, payload: bytearray) -> int:
        if frame_index == self.at_frame:
            return (counter + self.delta) % 256
        return counter


Scenario = Literal["clean", "noisy"]


@dataclass
class TrafficGenerator:
    # Emits frames at a fixed period.

    # Design goals:
    # - Clean by default
    # - Optional anomaly injection via an explicit list of Anomaly objects
    # - Clock is injectable for deterministic tests

    can_id: int = 0x123
    period_ms: int = 20
    source_node: str = "nodeA"
    channel: str = "can0"

    anomalies: List[Anomaly] = field(default_factory=list)

    fault_at: Optional[int] = None  # deprecated, use anomalies instead

    clock: Clock = field(default_factory=RealClock)

    def __post_init__(self) -> None:
        # Translate legacy fault_at into a real anomaly object
        if self.fault_at is not None:
            self.anomalies.append(CounterJumpAtFrame(at_frame=self.fault_at))

    def run(self, publish: Callable[[Frame], None], duration_s: float = 2.0) -> int:
        start = time.perf_counter()
        sent = 0
        counter = 0

        while (time.perf_counter() - start) < duration_s:
            payload = bytearray([counter, 0, 0, 0, 0, 0, 0, 0])

            # Apply anomalies deterministically by frame index
            for a in self.anomalies:
                counter = a.apply(frame_index=sent, counter=counter, payload=payload)
                payload[0] = counter  # keep byte0 consistent with counter

            # Normal increment for next frame
            counter = (counter + 1) % 256

            publish(
                Frame(
                    timestamp_ns=self.clock.time_ns(),
                    can_id=self.can_id,
                    data=bytes(payload),
                    channel=self.channel,
                    is_extended_id=False,
                    source_node=self.source_node,
                )
            )
            sent += 1
            self.clock.sleep(self.period_ms / 1000.0)

        return sent


def create_traffic_generator(
    *,
    scenario: Scenario = "clean",
    can_id: int = 0x123,
    period_ms: int = 20,
    fault_at: Optional[int] = None,
) -> TrafficGenerator:
    
    # Stable API for demo scripts

    # - scenario="clean": no anomalies unless explicitly provided via fault_at
    # - scenario="noisy": uses a default anomaly if none provided

    if scenario == "clean":
        return TrafficGenerator(can_id=can_id, period_ms=period_ms, fault_at=fault_at)

    # scenario == "noisy"
    if fault_at is None:
        fault_at = 80  # default demo anomaly
    return TrafficGenerator(can_id=can_id, period_ms=period_ms, fault_at=fault_at)
