from __future__ import annotations

import json
import logging
import math
import time
from collections.abc import Awaitable, Callable
from typing import Annotated, Any, TypeVar

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, TextContent
from pydantic import WithJsonSchema

from drumnext_mcp.api_client import DrumNextApiClient
from drumnext_mcp.errors import ErrorCode, McpToolError
from drumnext_mcp.models import PlaybackResult, PlaybackSnapshot, ScoreListResult, ScoreSummary

logger = logging.getLogger(__name__)

ResultT = TypeVar("ResultT", PlaybackSnapshot, PlaybackResult, ScoreListResult)

ScoreIdArgument = Annotated[
    Any,
    WithJsonSchema(
        {
            "anyOf": [
                {"type": "string", "minLength": 1, "maxLength": 64},
                {"type": "null"},
            ],
            "description": "乐谱 ID 或不区分大小写的完整标题；省略时播放当前乐谱。",
        }
    ),
]
PositionArgument = Annotated[
    Any,
    WithJsonSchema(
        {
            "type": "number",
            "minimum": 0,
            "description": "目标绝对位置，单位为秒，允许小数。",
        }
    ),
]
SpeedArgument = Annotated[
    Any,
    WithJsonSchema(
        {
            "type": "number",
            "minimum": 0.25,
            "maximum": 4.0,
            "description": "播放速度倍率，范围 0.25 到 4.0。",
        }
    ),
]


class DrumNextTools:
    def __init__(self, client: DrumNextApiClient, max_scores_returned: int) -> None:
        self._client = client
        self._max_scores_returned = max_scores_returned

    async def get_status(self) -> PlaybackSnapshot:
        return await self._client.get_status()

    async def list_scores(self) -> ScoreListResult:
        scores = await self._client.list_scores()
        return ScoreListResult(scores=scores[: self._max_scores_returned])

    async def play(self, score_id: Any = None) -> PlaybackResult:
        if score_id is None:
            playback = await self._client.play()
            return PlaybackResult(message="已开始播放", playback=playback)

        requested = _validate_score_id(score_id)
        scores = await self._client.list_scores()
        selected = self._resolve_score(requested, scores)
        latest = await self._client.change_score(selected.id)
        try:
            playback = await self._client.play()
        except McpToolError as error:
            raise error.with_details(
                playback=latest.model_dump(mode="json", by_alias=True)
            ) from None
        return PlaybackResult(message=f"已开始播放《{selected.title}》", playback=playback)

    async def pause(self) -> PlaybackResult:
        playback = await self._client.pause()
        return PlaybackResult(message="已暂停播放", playback=playback)

    async def resume(self) -> PlaybackResult:
        playback = await self._client.resume()
        return PlaybackResult(message="已恢复播放", playback=playback)

    async def stop(self) -> PlaybackResult:
        playback = await self._client.stop()
        return PlaybackResult(message="已停止播放并回到开头", playback=playback)

    async def seek(self, position_seconds: Any) -> PlaybackResult:
        position = _validate_number(position_seconds, name="position_seconds", minimum=0)
        playback = await self._client.seek(position * 1000)
        return PlaybackResult(message=f"已跳转到 {position:g} 秒", playback=playback)

    async def set_speed(self, speed: Any) -> PlaybackResult:
        value = _validate_number(speed, name="speed", minimum=0.25, maximum=4.0)
        playback = await self._client.set_speed(value)
        return PlaybackResult(message=f"播放速度已设置为 {value:g} 倍", playback=playback)

    def _resolve_score(self, requested: str, scores: list[ScoreSummary]) -> ScoreSummary:
        for score in scores:
            if score.id == requested:
                return score

        title_matches = [
            score for score in scores if score.title.casefold() == requested.casefold()
        ]
        if len(title_matches) == 1:
            return title_matches[0]

        candidates = title_matches or scores
        raise McpToolError.create(
            ErrorCode.SCORE_NOT_FOUND,
            "未找到唯一匹配的乐谱",
            retryable=False,
            details={
                "requested": requested,
                "candidates": [
                    score.model_dump(mode="json", by_alias=True)
                    for score in candidates[: self._max_scores_returned]
                ],
            },
        )


def register_tools(server: FastMCP, tools: DrumNextTools) -> None:
    @server.tool(
        name="drumnext_get_status",
        description="查询 DrumNext 当前权威播放状态；无副作用，返回位置、速度和乐谱。",
    )
    async def get_status() -> CallToolResult:
        return await _invoke("drumnext_get_status", tools.get_status)

    @server.tool(
        name="drumnext_list_scores",
        description="列出 DrumNext 可播放的乐谱摘要；无副作用，不返回完整音符。",
    )
    async def list_scores() -> CallToolResult:
        return await _invoke("drumnext_list_scores", tools.list_scores)

    @server.tool(
        name="drumnext_play",
        description=(
            "开始播放当前乐谱，或切换到指定乐谱后播放；会改变播放状态。"
            "score_id 必须是精确 ID 或完整标题。"
        ),
    )
    async def play(score_id: ScoreIdArgument = None) -> CallToolResult:
        return await _invoke("drumnext_play", lambda: tools.play(score_id))

    @server.tool(
        name="drumnext_pause",
        description="暂停当前播放；会改变播放状态，适用于正在播放时。",
    )
    async def pause() -> CallToolResult:
        return await _invoke("drumnext_pause", tools.pause)

    @server.tool(
        name="drumnext_resume",
        description="恢复已暂停的播放；会改变播放状态，适用于暂停时。",
    )
    async def resume() -> CallToolResult:
        return await _invoke("drumnext_resume", tools.resume)

    @server.tool(
        name="drumnext_stop",
        description="停止播放并回到乐谱开头；会改变播放状态。",
    )
    async def stop() -> CallToolResult:
        return await _invoke("drumnext_stop", tools.stop)

    @server.tool(
        name="drumnext_seek",
        description="跳转到乐谱的绝对时间位置；单位为秒，会改变播放位置。",
    )
    async def seek(position_seconds: PositionArgument) -> CallToolResult:
        return await _invoke("drumnext_seek", lambda: tools.seek(position_seconds))

    @server.tool(
        name="drumnext_set_speed",
        description="设置播放速度倍率；范围 0.25 到 4.0，会改变后续播放速度。",
    )
    async def set_speed(speed: SpeedArgument) -> CallToolResult:
        return await _invoke("drumnext_set_speed", lambda: tools.set_speed(speed))


async def _invoke(name: str, operation: Callable[[], Awaitable[ResultT]]) -> CallToolResult:
    started = time.perf_counter()
    try:
        result = await operation()
    except McpToolError as error:
        logger.warning(
            "tool=%s duration_ms=%.1f error=%s",
            name,
            (time.perf_counter() - started) * 1000,
            error.payload.code,
        )
        return error.as_call_result()
    except Exception:
        logger.exception(
            "tool=%s duration_ms=%.1f error=%s",
            name,
            (time.perf_counter() - started) * 1000,
            ErrorCode.BACKEND_FAILURE,
        )
        return McpToolError.create(
            ErrorCode.BACKEND_FAILURE,
            "工具执行失败",
            retryable=True,
        ).as_call_result()

    logger.info(
        "tool=%s duration_ms=%.1f success=true",
        name,
        (time.perf_counter() - started) * 1000,
    )
    payload = result.model_dump(mode="json", by_alias=True)
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return CallToolResult(
        isError=False,
        content=[TextContent(type="text", text=encoded)],
        structuredContent=payload,
    )


def _validate_score_id(value: Any) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 64:
        raise McpToolError.create(
            ErrorCode.INVALID_ARGUMENT,
            "score_id 必须是长度 1 到 64 的字符串",
            retryable=False,
        )
    return value


def _validate_number(
    value: Any,
    *,
    name: str,
    minimum: float,
    maximum: float | None = None,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        valid = False
    else:
        numeric = float(value)
        valid = math.isfinite(numeric) and numeric >= minimum
        if maximum is not None:
            valid = valid and numeric <= maximum
    if not valid:
        range_text = f"大于等于 {minimum:g}"
        if maximum is not None:
            range_text = f"{minimum:g} 到 {maximum:g} 之间"
        raise McpToolError.create(
            ErrorCode.INVALID_ARGUMENT,
            f"{name} 必须是{range_text}的有限数字",
            retryable=False,
        )
    return numeric
