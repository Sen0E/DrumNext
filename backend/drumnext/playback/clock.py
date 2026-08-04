import time
from typing import Protocol


class MonotonicClock(Protocol):
    def now_ms(self) -> float: ...


class SystemMonotonicClock:
    def now_ms(self) -> float:
        return time.monotonic_ns() / 1_000_000

