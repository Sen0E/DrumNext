import asyncio
import mimetypes
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response

from drumnext import __version__
from drumnext.api.content import router as content_router
from drumnext.api.health import router as health_router
from drumnext.api.playback import router as playback_router
from drumnext.config import Settings, settings
from drumnext.domain.protocol import ClockPing
from drumnext.playback.clock import SystemMonotonicClock
from drumnext.playback.scheduling import select_note_window
from drumnext.playback.service import PlaybackService
from drumnext.storage.content import ContentNotFoundError, LayoutStore, ScoreStore
from drumnext.transport.events import EventHub


def create_app(app_settings: Settings | None = None) -> FastAPI:
    resolved_settings = app_settings or settings
    app = FastAPI(title="DrumNext API", version=__version__)
    app.state.settings = resolved_settings
    clock = SystemMonotonicClock()
    scores = ScoreStore(resolved_settings.score_directory)
    try:
        default_score = scores.get(resolved_settings.default_score_id)
    except ContentNotFoundError:
        first_summary = scores.list()[0]
        default_score = scores.get(first_summary.id)
    app.state.playback = PlaybackService(
        clock, score_id=default_score.id, duration_ms=default_score.duration_ms
    )
    app.state.events = EventHub(clock)
    app.state.command_lock = asyncio.Lock()
    app.state.scores = scores
    app.state.layout = LayoutStore(
        resolved_settings.layout_file, resolved_settings.user_layout_file
    )
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(playback_router, prefix="/api/v1")
    app.include_router(content_router, prefix="/api/v1")

    @app.get("/debug/api", include_in_schema=False)
    async def api_debug_page() -> Response:
        page = Path(__file__).resolve().parent / "api-debug.html"
        return Response(page.read_bytes(), media_type="text/html")

    @app.exception_handler(ContentNotFoundError)
    async def content_not_found(
        _request: Request, error: ContentNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            {
                "error": {
                    "code": "SCORE_NOT_FOUND",
                    "message": "未找到指定乐谱",
                    "details": {"scoreId": str(error)},
                }
            },
            status_code=404,
        )

    @app.websocket("/ws/v1/projection")
    async def projection_socket(websocket: WebSocket) -> None:
        playback: PlaybackService = app.state.playback
        events: EventHub = app.state.events
        await events.connect(websocket, playback.snapshot())
        try:
            await _send_note_window(websocket, playback, events, app.state.scores)
            while True:
                ping = ClockPing.model_validate(await websocket.receive_json())
                pong = await events.envelope(
                    "clock.pong", {"clientTimeMs": ping.client_time_ms}
                )
                await events.send(websocket, pong)
                await _send_note_window(websocket, playback, events, app.state.scores)
        except WebSocketDisconnect:
            pass
        finally:
            events.disconnect(websocket)

    _mount_projection(app, resolved_settings.projection_dist)
    return app


async def _send_note_window(
    websocket: WebSocket,
    playback: PlaybackService,
    events: EventHub,
    scores: ScoreStore,
) -> None:
    snapshot = playback.snapshot()
    score = scores.get(snapshot.score_id)
    notes = select_note_window(score, snapshot.position_ms)
    message = await events.envelope(
        "notes.scheduled",
        {
            "scoreId": score.id,
            "windowStartMs": snapshot.position_ms,
            "windowEndMs": min(score.duration_ms, snapshot.position_ms + 4_000),
            "notes": [note.model_dump(by_alias=True, mode="json") for note in notes],
        },
    )
    await events.send(websocket, message)


def _mount_projection(app: FastAPI, distribution: Path) -> None:
    index = distribution / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    async def projection(path: str) -> Response:
        candidate = (distribution / path).resolve()
        root = distribution.resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            media_type, _ = mimetypes.guess_type(candidate.name)
            return Response(candidate.read_bytes(), media_type=media_type)
        if index.is_file():
            return Response(index.read_bytes(), media_type="text/html")
        unavailable_page = Path(__file__).resolve().parent / "static-unavailable.html"
        return Response(unavailable_page.read_bytes(), status_code=503, media_type="text/html")


app = create_app()


def run() -> None:
    uvicorn.run("drumnext.main:app", host=settings.host, port=settings.port)
