import asyncio
from dataclasses import dataclass

from drumnext.domain.protocol import PlaybackSnapshot
from drumnext.playback.clock import MonotonicClock


@dataclass
class PlaybackState:
    status: str
    score_id: str
    duration_ms: int
    anchor_position_ms: float
    anchor_clock_ms: float
    speed: float


class PlaybackService:
    def __init__(
        self,
        clock: MonotonicClock,
        *,
        score_id: str = "demo-score",
        duration_ms: int = 16_000,
    ) -> None:
        now_ms = clock.now_ms()
        self._clock = clock
        self._lock = asyncio.Lock()
        self._state = PlaybackState("stopped", score_id, duration_ms, 0, now_ms, 1)

    def snapshot(self) -> PlaybackSnapshot:
        now_ms = self._clock.now_ms()
        position_ms = self._position_at(now_ms)
        state = self._state
        return PlaybackSnapshot(
            status=state.status,
            scoreId=state.score_id,
            durationMs=state.duration_ms,
            positionMs=position_ms,
            anchorPositionMs=state.anchor_position_ms,
            anchorClockMs=state.anchor_clock_ms,
            speed=state.speed,
        )

    async def play(self) -> PlaybackSnapshot:
        async with self._lock:
            now_ms = self._clock.now_ms()
            position_ms = 0 if self._state.status == "stopped" else self._position_at(now_ms)
            self._reanchor("playing", position_ms, now_ms)
            return self.snapshot()

    async def pause(self) -> PlaybackSnapshot:
        async with self._lock:
            if self._state.status == "playing":
                now_ms = self._clock.now_ms()
                self._reanchor("paused", self._position_at(now_ms), now_ms)
            return self.snapshot()

    async def resume(self) -> PlaybackSnapshot:
        async with self._lock:
            if self._state.status == "paused":
                now_ms = self._clock.now_ms()
                self._reanchor("playing", self._state.anchor_position_ms, now_ms)
            return self.snapshot()

    async def stop(self) -> PlaybackSnapshot:
        async with self._lock:
            self._reanchor("stopped", 0, self._clock.now_ms())
            return self.snapshot()

    async def seek(self, position_ms: float) -> PlaybackSnapshot:
        async with self._lock:
            now_ms = self._clock.now_ms()
            bounded_position = min(max(position_ms, 0), self._state.duration_ms)
            self._reanchor(self._state.status, bounded_position, now_ms)
            return self.snapshot()

    async def set_speed(self, speed: float) -> PlaybackSnapshot:
        async with self._lock:
            now_ms = self._clock.now_ms()
            position_ms = self._position_at(now_ms)
            self._state.speed = speed
            self._state.anchor_position_ms = position_ms
            self._state.anchor_clock_ms = now_ms
            return self.snapshot()

    async def change_score(self, score_id: str, duration_ms: int) -> PlaybackSnapshot:
        async with self._lock:
            self._state.score_id = score_id
            self._state.duration_ms = duration_ms
            self._reanchor("stopped", 0, self._clock.now_ms())
            return self.snapshot()

    def _position_at(self, now_ms: float) -> float:
        state = self._state
        if state.status != "playing":
            return state.anchor_position_ms
        elapsed_ms = (now_ms - state.anchor_clock_ms) * state.speed
        return min(state.anchor_position_ms + elapsed_ms, state.duration_ms)

    def _reanchor(self, status: str, position_ms: float, clock_ms: float) -> None:
        self._state.status = status
        self._state.anchor_position_ms = position_ms
        self._state.anchor_clock_ms = clock_ms
