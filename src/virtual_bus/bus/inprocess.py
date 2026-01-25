from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List
import threading

from .types import Frame


Subscriber = Callable[[Frame], None]


@dataclass
class InProcessBus:
    # Minimal in-process CAN bus:
    # - broadcast semantics: every published Frame goes to every subscriber
    # - synchronous delivery (simple + deterministic for now)

    _subs: List[Subscriber] = None

    def __post_init__(self) -> None:
        if self._subs is None:
            self._subs = []
        self._lock = threading.Lock()

    def subscribe(self, fn: Subscriber) -> None:
        with self._lock:
            self._subs.append(fn)

    def publish(self, frame: Frame) -> None:
        # Copy under lock to avoid issues if subscribers change mid-publish
        with self._lock:
            subs = list(self._subs)
        for fn in subs:
            fn(frame)
