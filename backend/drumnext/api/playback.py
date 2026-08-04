from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from drumnext.domain.protocol import PlaybackSnapshot
from drumnext.playback.service import PlaybackService
from drumnext.transport.events import EventHub

router = APIRouter(prefix="/playback", tags=["playback"])


class SeekRequest(BaseModel):
    position_ms: float = Field(alias="positionMs", ge=0)


class SpeedRequest(BaseModel):
    speed: float = Field(ge=0.25, le=4)


class ChangeScoreRequest(BaseModel):
    score_id: str = Field(alias="scoreId", min_length=1, max_length=64)


def _services(request: Request) -> tuple[PlaybackService, EventHub]:
    return request.app.state.playback, request.app.state.events


async def _command(
    request: Request,
    event_type: str,
    action: Callable[[], Awaitable[PlaybackSnapshot]],
) -> PlaybackSnapshot:
    _, events = _services(request)
    async with request.app.state.command_lock:
        snapshot = await action()
        await events.broadcast_snapshot(event_type, snapshot)
        return snapshot


@router.get("", response_model=PlaybackSnapshot)
async def get_playback(request: Request) -> PlaybackSnapshot:
    playback, _ = _services(request)
    return playback.snapshot()


@router.post("/play", response_model=PlaybackSnapshot)
async def play(request: Request) -> PlaybackSnapshot:
    playback, _ = _services(request)
    return await _command(request, "playback.started", playback.play)


@router.post("/pause", response_model=PlaybackSnapshot)
async def pause(request: Request) -> PlaybackSnapshot:
    playback, _ = _services(request)
    return await _command(request, "playback.paused", playback.pause)


@router.post("/resume", response_model=PlaybackSnapshot)
async def resume(request: Request) -> PlaybackSnapshot:
    playback, _ = _services(request)
    return await _command(request, "playback.resumed", playback.resume)


@router.post("/stop", response_model=PlaybackSnapshot)
async def stop(request: Request) -> PlaybackSnapshot:
    playback, _ = _services(request)
    return await _command(request, "playback.stopped", playback.stop)


@router.post("/seek", response_model=PlaybackSnapshot)
async def seek(body: SeekRequest, request: Request) -> PlaybackSnapshot:
    playback, _ = _services(request)
    return await _command(request, "playback.seeked", lambda: playback.seek(body.position_ms))


@router.post("/speed", response_model=PlaybackSnapshot)
async def speed(body: SpeedRequest, request: Request) -> PlaybackSnapshot:
    playback, _ = _services(request)
    return await _command(
        request, "playback.speed_changed", lambda: playback.set_speed(body.speed)
    )


@router.post("/score", response_model=PlaybackSnapshot)
async def change_score(body: ChangeScoreRequest, request: Request) -> PlaybackSnapshot:
    playback, _ = _services(request)
    score = request.app.state.scores.get(body.score_id)
    return await _command(
        request,
        "score.changed",
        lambda: playback.change_score(score.id, score.duration_ms),
    )
