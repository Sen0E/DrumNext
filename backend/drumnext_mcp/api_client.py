from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from pydantic import HttpUrl, TypeAdapter, ValidationError

from drumnext_mcp.errors import ErrorCode, McpToolError
from drumnext_mcp.models import PlaybackSnapshot, ScoreSummary

logger = logging.getLogger(__name__)

_SCORES_PATH = "/api/v1/scores"
_PLAYBACK_PATH = "/api/v1/playback"
_PLAY_PATH = "/api/v1/playback/play"
_PAUSE_PATH = "/api/v1/playback/pause"
_RESUME_PATH = "/api/v1/playback/resume"
_STOP_PATH = "/api/v1/playback/stop"
_SEEK_PATH = "/api/v1/playback/seek"
_SPEED_PATH = "/api/v1/playback/speed"
_SCORE_PATH = "/api/v1/playback/score"

_SCORE_LIST_ADAPTER = TypeAdapter(list[ScoreSummary])


class DrumNextApiClient:
    """A deliberately restricted client for the public DrumNext playback API."""

    def __init__(
        self,
        base_url: HttpUrl,
        request_timeout_seconds: float,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=str(base_url),
            timeout=request_timeout_seconds,
            transport=transport,
            follow_redirects=False,
        )

    async def __aenter__(self) -> DrumNextApiClient:
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_status(self) -> PlaybackSnapshot:
        payload = await self._request_json("GET", _PLAYBACK_PATH)
        return self._validate_playback(payload)

    async def list_scores(self) -> list[ScoreSummary]:
        payload = await self._request_json("GET", _SCORES_PATH)
        try:
            return _SCORE_LIST_ADAPTER.validate_python(payload)
        except ValidationError:
            raise _invalid_backend_response() from None

    async def play(self) -> PlaybackSnapshot:
        return await self._playback_command(_PLAY_PATH)

    async def pause(self) -> PlaybackSnapshot:
        return await self._playback_command(_PAUSE_PATH)

    async def resume(self) -> PlaybackSnapshot:
        return await self._playback_command(_RESUME_PATH)

    async def stop(self) -> PlaybackSnapshot:
        return await self._playback_command(_STOP_PATH)

    async def seek(self, position_ms: float) -> PlaybackSnapshot:
        return await self._playback_command(_SEEK_PATH, {"positionMs": position_ms})

    async def set_speed(self, speed: float) -> PlaybackSnapshot:
        return await self._playback_command(_SPEED_PATH, {"speed": speed})

    async def change_score(self, score_id: str) -> PlaybackSnapshot:
        return await self._playback_command(_SCORE_PATH, {"scoreId": score_id})

    async def _playback_command(
        self, path: str, body: dict[str, Any] | None = None
    ) -> PlaybackSnapshot:
        payload = await self._request_json("POST", path, body)
        return self._validate_playback(payload)

    async def _request_json(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> Any:
        started = time.perf_counter()
        try:
            response = await self._client.request(method, path, json=body)
        except (httpx.TimeoutException, httpx.NetworkError):
            logger.warning(
                "REST %s %s unavailable duration_ms=%.1f",
                method,
                path,
                (time.perf_counter() - started) * 1000,
            )
            raise McpToolError.create(
                ErrorCode.BACKEND_UNAVAILABLE,
                "DrumNext 服务当前不可用",
                retryable=True,
            ) from None
        except httpx.RequestError:
            logger.warning(
                "REST %s %s failed duration_ms=%.1f",
                method,
                path,
                (time.perf_counter() - started) * 1000,
            )
            raise McpToolError.create(
                ErrorCode.BACKEND_UNAVAILABLE,
                "DrumNext 服务当前不可用",
                retryable=True,
            ) from None

        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "REST %s %s status=%d duration_ms=%.1f",
            method,
            path,
            response.status_code,
            elapsed_ms,
        )
        if 400 <= response.status_code < 500:
            raise McpToolError.create(
                ErrorCode.BACKEND_REJECTED,
                "DrumNext 服务拒绝了请求",
                retryable=response.status_code in {408, 429},
                details={"statusCode": response.status_code},
            )
        if response.status_code >= 500:
            raise McpToolError.create(
                ErrorCode.BACKEND_FAILURE,
                "DrumNext 服务返回错误",
                retryable=True,
                details={"statusCode": response.status_code},
            )

        try:
            return response.json()
        except ValueError:
            raise _invalid_backend_response() from None

    @staticmethod
    def _validate_playback(payload: Any) -> PlaybackSnapshot:
        try:
            return PlaybackSnapshot.model_validate(payload)
        except ValidationError:
            raise _invalid_backend_response() from None


def _invalid_backend_response() -> McpToolError:
    return McpToolError.create(
        ErrorCode.BACKEND_FAILURE,
        "DrumNext 服务返回了无效响应",
        retryable=True,
    )
