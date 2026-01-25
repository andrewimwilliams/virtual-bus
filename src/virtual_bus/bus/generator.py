from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional

from .types import Frame


@dataclass
class TrafficGenerator:
    # Simple generator:
    # - emits one ID at a given period
    # - increments a counter in payload[0]
    # - after 'fault_at' frames, jumps the counter to simulate an anomaly

    can_id: int = 0x123
    period_ms: int = 20
    fault_at: Optional[int] = 80  # inject anomaly at this frame index
    source_node: str = "nodeA"
    channel: str = "can0"

    def run(self, publish: Callable[[Frame], None], duration_s: float = 2.0) -> int:
        start = time.perf_counter()
        sent = 0
        counter = 0

        while (time.perf_counter() - start) < duration_s:
            if self.fault_at is not None and sent == self.fault_at:
                counter = (counter + 50) % 256  # jump -> anomaly

            data = bytes([counter, 0, 0, 0, 0, 0, 0, 0])
            counter = (counter + 1) % 256

            ts_ns = time.time_ns()
            publish(
                Frame(
                    timestamp_ns=ts_ns,
                    can_id=self.can_id,
                    data=data,
                    channel=self.channel,
                    is_extended_id=False,
                    source_node=self.source_node,
                )
            )
            sent += 1
            time.sleep(self.period_ms / 1000.0)

        return sent
