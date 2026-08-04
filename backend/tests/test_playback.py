import pytest

from drumnext.playback.service import PlaybackService


class FakeClock:
    def __init__(self, now_ms: float = 1_000) -> None:
        self.value = now_ms

    def now_ms(self) -> float:
        return self.value


@pytest.mark.anyio
async def test_playback_uses_absolute_anchor_formula() -> None:
    clock = FakeClock()
    playback = PlaybackService(clock)
    await playback.play()
    clock.value = 2_250

    assert playback.snapshot().position_ms == 1_250


@pytest.mark.anyio
async def test_pause_resume_speed_and_seek_reanchor_without_drift() -> None:
    clock = FakeClock()
    playback = PlaybackService(clock)
    await playback.play()
    clock.value = 2_000
    paused = await playback.pause()
    clock.value = 8_000
    assert playback.snapshot().position_ms == paused.position_ms == 1_000

    await playback.set_speed(2)
    await playback.resume()
    clock.value = 8_500
    assert playback.snapshot().position_ms == 2_000

    seeked = await playback.seek(15_500)
    assert seeked.position_ms == 15_500
    clock.value = 9_000
    assert playback.snapshot().position_ms == 16_000


@pytest.mark.anyio
async def test_stop_is_idempotent() -> None:
    clock = FakeClock()
    playback = PlaybackService(clock)
    await playback.play()
    first = await playback.stop()
    second = await playback.stop()
    assert first.status == second.status == "stopped"
    assert first.position_ms == second.position_ms == 0
