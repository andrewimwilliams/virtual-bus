from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Callable, Optional, Protocol, Literal, List, Dict, Any, Tuple

from .types import Frame


# -------------------------
# Clock abstraction
# -------------------------

class Clock(Protocol):
    def time_ns(self) -> int: ...
    def sleep(self, seconds: float) -> None: ...

@dataclass
class RealClock:
    def time_ns(self) -> int:
        return time.time_ns()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


# -------------------------
# Frame sources
# -------------------------

@dataclass(frozen=True)
class FrameSource:
    can_id: int
    name: str
    payload_len: int = 8

    def step(self, state: Dict[str, Any], rng: random.Random) -> bytearray:
        raise NotImplementedError

@dataclass(frozen=True)
class CounterSource(FrameSource):

    # Byte 0 is a mod-256 counter

    can_id: int = 0x123
    name: str = "counter_frame"
    payload_len: int = 8

    def step(self, state: Dict[str, Any], rng: random.Random) -> bytearray:
        counter = int(state.get("counter", 0)) % 256
        payload = bytearray([counter] + [0] * (self.payload_len - 1))
        state["counter"] = (counter + 1) % 256
        return payload

@dataclass(frozen=True)
class TemperatureSource(FrameSource):

    # Bytes 0-1 hold temperature in deci-degrees C (251 = 25.1C)
    # Deterministic drift

    can_id: int = 0x124
    name: str = "temp_frame"
    payload_len: int = 8
    start_deci_c: int = 250  # 25.0C
    step_deci_c: int = 1     # +0.1C per emission
    min_deci_c: int = 180    # 18.0C
    max_deci_c: int = 320    # 32.0C

    def step(self, state: Dict[str, Any], rng: random.Random) -> bytearray:
        t = int(state.get("temp_deci_c", self.start_deci_c))
        # Simple bounded sawtooth drift
        direction = int(state.get("temp_dir", 1))
        t_next = t + direction * self.step_deci_c
        if t_next > self.max_deci_c:
            t_next = self.max_deci_c
            direction = -1
        elif t_next < self.min_deci_c:
            t_next = self.min_deci_c
            direction = 1

        state["temp_deci_c"] = t_next
        state["temp_dir"] = direction

        payload = bytearray([0] * self.payload_len)
        payload[0:2] = int(t_next).to_bytes(2, byteorder="little", signed=False)
        return payload

@dataclass(frozen=True)
class VoltageSource(FrameSource):

    # Bytes 0-1 hold millivolts (12050 = 12.050V)
    # Deterministic ripple pattern
    
    can_id: int = 0x125
    name: str = "volt_frame"
    payload_len: int = 8
    base_mv: int = 12000
    ripple_mv: int = 30

    def step(self, state: Dict[str, Any], rng: random.Random) -> bytearray:
        phase = int(state.get("phase", 0))
        # Deterministic triangle-ish ripple
        r = self.ripple_mv
        cycle = 4 * r
        x = phase % cycle
        if x <= r:
            dv = x
        elif x <= 2 * r:
            dv = 2 * r - x
        elif x <= 3 * r:
            dv = -(x - 2 * r)
        else:
            dv = -(4 * r - x)

        mv = self.base_mv + dv
        state["phase"] = phase + 1

        payload = bytearray([0] * self.payload_len)
        payload[0:2] = int(mv).to_bytes(2, byteorder="little", signed=False)
        return payload


# -------------------------
# Anomaly injection
# -------------------------

class Anomaly(Protocol):

    # An anomaly can probabilistically mutate the payload/state for a given frame
    # Return True if it fired, else False
    
    def maybe_apply(
        self,
        *,
        rng: random.Random,
        frame_index: int,
        can_id: int,
        payload: bytearray,
        state: Dict[str, Any],
    ) -> bool: ...

@dataclass(frozen=True)
class ProbCounterJump:
    
    # With probability p, apply a counter jump to byte0 (mod 256) on the target CAN ID.

    p: float = 0.001
    delta_range: Tuple[int, int] = (10, 80)
    target_can_id: int = 0x123

    def maybe_apply(
        self,
        *,
        rng: random.Random,
        frame_index: int,
        can_id: int,
        payload: bytearray,
        state: Dict[str, Any],
    ) -> bool:
        if can_id != self.target_can_id:
            return False
        if rng.random() >= self.p:
            return False

        lo, hi = self.delta_range
        delta = rng.randint(lo, hi)
        payload[0] = (payload[0] + delta) % 256
        return True
    
@dataclass(frozen=True)
class ProbTemperatureSpike:

    # With probability p, spike temperature (byte 0-1, deci-degC) on the target CAN ID.

    p: float = 0.001
    delta_range: Tuple[int, int] = (-50, 50)    # +/- 5.0C
    target_can_id: int = 0x124

    def maybe_apply(
        self,
        *,
        rng: random.Random,
        frame_index: int,
        can_id: int,
        payload: bytearray,
        state: Dict[str, Any],
    ) -> bool:
        if can_id != self.target_can_id:
            return False
        if rng.random() >= self.p:
            return False

        lo, hi = self.delta_range
        delta = 0
        while delta == 0:
            delta = rng.randint(lo, hi)
        
        t = int.from_bytes(payload[0:2], byteorder="little", signed=False)
        t2 = max(0, min(0xFFFF, t + delta))
        payload[0:2] = int(t2).to_bytes(2, byteorder="little", signed=False)
        return True
    
@dataclass(frozen=True)
class ProbVoltageSpike:
    
    # With probability p, spike voltage (bytes 0-1, millivolts) on the target CAN ID.

    p: float = 0.001
    delta_range: Tuple[int, int] = (-1200, 1200)  # +/- 1.2V
    target_can_id: int = 0x125

    def maybe_apply(
        self,
        *,
        rng: random.Random,
        frame_index: int,
        can_id: int,
        payload: bytearray,
        state: Dict[str, Any],
    ) -> bool:
        if can_id != self.target_can_id:
            return False
        if rng.random() >= self.p:
            return False

        lo, hi = self.delta_range
        delta = 0
        while delta == 0:
            delta = rng.randint(lo, hi)

        mv = int.from_bytes(payload[0:2], byteorder="little", signed=False)
        mv2 = max(0, min(0xFFFF, mv + delta))
        payload[0:2] = int(mv2).to_bytes(2, byteorder="little", signed=False)
        return True


# -------------------------
# Generator
# -------------------------

Scenario = Literal["clean", "noisy"]
Profile = Literal["single", "multi"]

@dataclass
class TrafficGenerator:
    # Emits frames at a fixed period, selecting from one or more FrameSources.

    # Goals:
    # - Clean by default
    # - Multi-CAN via sources (each has its own state)
    # - Probabilistic anomalies (seedable)
    # - Clock is injectable for deterministic tests

    period_ms: int = 20
    source_node: str = "nodeA"
    channel: str = "can0"

    sources: List[FrameSource] = field(default_factory=list)
    anomalies: List[Anomaly] = field(default_factory=list)

    seed: Optional[int] = None
    clock: Clock = field(default_factory=RealClock)

    def __post_init__(self) -> None:
        if not self.sources:
            # Backward-compatible default: single counter source only.
            self.sources = [CounterSource()]

        self._rng = random.Random(self.seed)
        self._state_by_id: Dict[int, Dict[str, Any]] = {s.can_id: {} for s in self.sources}

    def run(self, publish: Callable[[Frame], None], duration_s: float = 2.0) -> int:
        start = time.perf_counter()
        sent = 0

        n = len(self.sources)
        if n == 0:
            return 0

        while (time.perf_counter() - start) < duration_s:
            # Round-robin across sources so total rate stays ~1/period_ms
            src = self.sources[sent % n]
            state = self._state_by_id[src.can_id]
            payload = src.step(state, self._rng)

            # Apply anomalies probabilistically
            for a in self.anomalies:
                a.maybe_apply(
                    rng=self._rng,
                    frame_index=sent,
                    can_id=src.can_id,
                    payload=payload,
                    state=state,
                )

            publish(
                Frame(
                    timestamp_ns=self.clock.time_ns(),
                    can_id=src.can_id,
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
    profile: Profile = "single",
    period_ms: int = 20,
    seed: Optional[int] = None,
    anomaly_rate: float = 0.001,
) -> TrafficGenerator:
    # Stable factory API for demo scripts.

    # - scenario="clean": no anomalies
    # - scenario="noisy": adds probabilistic anomalies by default
    # - profile="single": only 0x123 counter frames
    # - profile="multi": emits several CAN IDs (richer signal space)
    
    sources: List[FrameSource]
    if profile == "single":
        sources = [CounterSource()]
    else:
        sources = [CounterSource(), TemperatureSource(), VoltageSource()]

    anomalies: List[Anomaly] = []
    if scenario == "noisy":
        if anomaly_rate < 0.0 or anomaly_rate > 1.0:
            raise ValueError("anomaly_rate must be between 0.0 and 1.0")
        if anomaly_rate > 0.0:
            anomalies.append(
                ProbCounterJump(p=anomaly_rate, delta_range=(10, 80), target_can_id=0x123)
            )
            anomalies.append(
                ProbTemperatureSpike(p=anomaly_rate, delta_range=(-50, 50), target_can_id=0x124)
            )
            anomalies.append(
                ProbVoltageSpike(p=anomaly_rate, delta_range=(-1200, 1200), target_can_id=0x125)
            )

    return TrafficGenerator(
        period_ms=period_ms,
        sources=sources,
        anomalies=anomalies,
        seed=seed,
    )

