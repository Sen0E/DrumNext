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
            "description": (
                "空灵鼓投影乐谱的 ID 或不区分大小写的完整标题；"
                "省略时从当前位置播放当前投影乐谱。"
            ),
        }
    ),
]
PositionArgument = Annotated[
    Any,
    WithJsonSchema(
        {
            "type": "number",
            "minimum": 0,
            "description": "空灵鼓投影时间轴的目标绝对位置，单位为秒，允许小数。",
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
            "description": "空灵鼓投影乐谱演示的速度倍率，范围 0.25 到 4.0。",
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
            return PlaybackResult(message="空灵鼓投影已开始播放", playback=playback)

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
        return PlaybackResult(
            message=f"空灵鼓投影已开始播放乐谱《{selected.title}》",
            playback=playback,
        )

    async def pause(self) -> PlaybackResult:
        playback = await self._client.pause()
        return PlaybackResult(message="空灵鼓投影已暂停", playback=playback)

    async def resume(self) -> PlaybackResult:
        playback = await self._client.resume()
        return PlaybackResult(message="空灵鼓投影已从暂停位置继续", playback=playback)

    async def stop(self) -> PlaybackResult:
        playback = await self._client.stop()
        return PlaybackResult(message="空灵鼓投影已停止并回到乐谱开头", playback=playback)

    async def seek(self, position_seconds: Any) -> PlaybackResult:
        position = _validate_number(position_seconds, name="position_seconds", minimum=0)
        playback = await self._client.seek(position * 1000)
        return PlaybackResult(
            message=f"空灵鼓投影已跳转到 {position:g} 秒", playback=playback
        )

    async def set_speed(self, speed: Any) -> PlaybackResult:
        value = _validate_number(speed, name="speed", minimum=0.25, maximum=4.0)
        playback = await self._client.set_speed(value)
        return PlaybackResult(
            message=f"空灵鼓投影速度已设置为 {value:g} 倍", playback=playback
        )

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
        title="查询空灵鼓投影状态",
        description=(
            "查询空灵鼓演奏引导投影的当前状态；无副作用。"
            "当用户询问投影是否在播放、播到哪里、当前乐谱或速度时使用，"
            "返回投影状态、乐谱、时间轴位置和速度。"
        ),
    )
    async def get_status() -> CallToolResult:
        return await _invoke("drumnext_get_status", tools.get_status)

    @server.tool(
        name="drumnext_list_scores",
        title="列出空灵鼓投影乐谱",
        description=(
            "列出空灵鼓投影系统可以演示的乐谱；无副作用。"
            "当用户询问有哪些曲目或可播放什么时使用，只返回乐谱摘要，不返回完整音符。"
        ),
    )
    async def list_scores() -> CallToolResult:
        return await _invoke("drumnext_list_scores", tools.list_scores)

    @server.tool(
        name="drumnext_play",
        title="播放空灵鼓投影乐谱",
        description=(
            "开始推进空灵鼓演奏引导投影的乐谱时间轴；会立即改变现场投影状态。"
            "可以继续播放当前投影乐谱，也可以先切换到指定乐谱再播放。"
            "score_id 必须是精确乐谱 ID 或完整标题；不要用它控制普通音乐或视频。"
        ),
    )
    async def play(score_id: ScoreIdArgument = None) -> CallToolResult:
        return await _invoke("drumnext_play", lambda: tools.play(score_id))

    @server.tool(
        name="drumnext_pause",
        title="暂停空灵鼓投影",
        description=(
            "暂停正在推进的空灵鼓投影乐谱时间轴，使演奏引导画面停在当前位置；"
            "会立即改变现场投影状态，适用于投影正在播放时。"
        ),
    )
    async def pause() -> CallToolResult:
        return await _invoke("drumnext_pause", tools.pause)

    @server.tool(
        name="drumnext_resume",
        title="继续空灵鼓投影",
        description=(
            "让已暂停的空灵鼓投影从当前位置继续推进乐谱时间轴；"
            "会立即改变现场投影状态，适用于投影已暂停时。"
        ),
    )
    async def resume() -> CallToolResult:
        return await _invoke("drumnext_resume", tools.resume)

    @server.tool(
        name="drumnext_stop",
        title="停止空灵鼓投影",
        description=(
            "停止空灵鼓演奏引导投影，并把当前乐谱的投影时间轴归零回到开头；"
            "会立即改变现场投影状态。"
        ),
    )
    async def stop() -> CallToolResult:
        return await _invoke("drumnext_stop", tools.stop)

    @server.tool(
        name="drumnext_seek",
        title="跳转空灵鼓投影进度",
        description=(
            "把空灵鼓投影乐谱的时间轴跳转到指定绝对位置；单位为秒，允许小数。"
            "当用户要求投影跳到某个时间点、从某处开始或调整演示进度时使用。"
        ),
    )
    async def seek(position_seconds: PositionArgument) -> CallToolResult:
        return await _invoke("drumnext_seek", lambda: tools.seek(position_seconds))

    @server.tool(
        name="drumnext_set_speed",
        title="设置空灵鼓投影速度",
        description=(
            "设置空灵鼓投影乐谱时间轴的演示速度倍率；范围 0.25 到 4.0。"
            "会立即改变后续投影节奏，不用于调节音量。"
        ),
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
