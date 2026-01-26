from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, List, TypeVar
import threading

T = TypeVar("T")
Subscriber = Callable[[T], None]


@dataclass
class Bus(Generic[T]):
    # Minimal in-process pub/sub bus.

    # Semantics:
    # - broadcast: each publish() goes to every subscriber
    # - synchronous: delivery happens immediately in the publisher's thread
    # - deterministic ordering: subscribers are called in subscription order

    _subs: List[Subscriber[T]] = None

    def __post_init__(self) -> None:
        if self._subs is None:
            self._subs = []
        self._lock = threading.Lock()

    def subscribe(self, fn: Subscriber[T]) -> None:
        with self._lock:
            self._subs.append(fn)

    def publish(self, msg: T) -> None:
        with self._lock:
            subs = list(self._subs)
        for fn in subs:
            fn(msg)
