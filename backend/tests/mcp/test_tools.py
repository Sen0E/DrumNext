from __future__ import annotations

import json
from typing import Any

import pytest

from drumnext_mcp.errors import ErrorCode, McpToolError
from drumnext_mcp.models import PlaybackSnapshot, ScoreSummary
from drumnext_mcp.server import create_server
from drumnext_mcp.tools import DrumNextTools


def snapshot(**updates: Any) -> PlaybackSnapshot:
    payload: dict[str, Any] = {
        "status": "playing",
        "scoreId": "first",
        "durationMs": 10_000,
        "positionMs": 0,
        "anchorPositionMs": 0,
        "anchorClockMs": 100.0,
        "speed": 1.0,
    }
    payload.update(updates)
    return PlaybackSnapshot.model_validate(payload)


def score(identifier: str, title: str) -> ScoreSummary:
    return ScoreSummary.model_validate(
        {
            "id": identifier,
            "title": title,
            "durationMs": 10_000,
            "noteCount": 5,
        }
    )


class FakeClient:
    def __init__(self) -> None:
        self.scores = [score("first", "大鱼"), score("second", "小星星")]
        self.calls: list[tuple[str, Any]] = []
        self.play_error: McpToolError | None = None

    async def get_status(self) -> PlaybackSnapshot:
        self.calls.append(("get_status", None))
        return snapshot()

    async def list_scores(self) -> list[ScoreSummary]:
        self.calls.append(("list_scores", None))
        return self.scores

    async def play(self) -> PlaybackSnapshot:
        self.calls.append(("play", None))
        if self.play_error is not None:
            raise self.play_error
        return snapshot()

    async def pause(self) -> PlaybackSnapshot:
        self.calls.append(("pause", None))
        return snapshot(status="paused")

    async def resume(self) -> PlaybackSnapshot:
        self.calls.append(("resume", None))
        return snapshot()

    async def stop(self) -> PlaybackSnapshot:
        self.calls.append(("stop", None))
        return snapshot(status="stopped")

    async def seek(self, position_ms: float) -> PlaybackSnapshot:
        self.calls.append(("seek", position_ms))
        return snapshot(positionMs=position_ms)

    async def set_speed(self, speed: float) -> PlaybackSnapshot:
        self.calls.append(("set_speed", speed))
        return snapshot(speed=speed)

    async def change_score(self, score_id: str) -> PlaybackSnapshot:
        self.calls.append(("change_score", score_id))
        return snapshot(status="stopped", scoreId=score_id)

    async def aclose(self) -> None:
        pass


def make_tools(client: FakeClient, maximum: int = 100) -> DrumNextTools:
    return DrumNextTools(client, maximum)  # type: ignore[arg-type]


@pytest.mark.anyio
async def test_list_is_limited_and_contains_only_summaries() -> None:
    client = FakeClient()
    client.scores.append(score("third", "第三首"))

    result = await make_tools(client, maximum=2).list_scores()

    assert [item.id for item in result.scores] == ["first", "second"]
    serialized = result.model_dump(mode="json", by_alias=True)
    assert "notes" not in json.dumps(serialized)


@pytest.mark.anyio
async def test_play_without_score_only_calls_play() -> None:
    client = FakeClient()

    result = await make_tools(client).play()

    assert result.playback.status == "playing"
    assert client.calls == [("play", None)]


@pytest.mark.anyio
async def test_score_id_has_priority_over_an_identical_title() -> None:
    client = FakeClient()
    client.scores = [score("大鱼", "ID 优先"), score("other", "大鱼")]

    result = await make_tools(client).play("大鱼")

    assert result.message == "空灵鼓投影已开始播放乐谱《ID 优先》"
    assert client.calls == [
        ("list_scores", None),
        ("change_score", "大鱼"),
        ("play", None),
    ]


@pytest.mark.anyio
async def test_title_match_is_complete_and_case_insensitive() -> None:
    client = FakeClient()
    client.scores = [score("exact", "Demo Song")]

    await make_tools(client).play("demo song")

    assert client.calls[1] == ("change_score", "exact")


@pytest.mark.anyio
@pytest.mark.parametrize("requested", ["鱼", "missing"])
async def test_score_does_not_use_partial_or_fuzzy_matching(requested: str) -> None:
    client = FakeClient()

    with pytest.raises(McpToolError) as captured:
        await make_tools(client, maximum=1).play(requested)

    assert captured.value.payload.code == ErrorCode.SCORE_NOT_FOUND
    candidates = captured.value.payload.details["candidates"]
    assert len(candidates) == 1
    assert client.calls == [("list_scores", None)]


@pytest.mark.anyio
async def test_duplicate_complete_titles_are_not_treated_as_unique() -> None:
    client = FakeClient()
    client.scores = [score("one", "Same"), score("two", "same")]

    with pytest.raises(McpToolError) as captured:
        await make_tools(client).play("SAME")

    assert captured.value.payload.code == ErrorCode.SCORE_NOT_FOUND
    assert [item["id"] for item in captured.value.payload.details["candidates"]] == [
        "one",
        "two",
    ]


@pytest.mark.anyio
async def test_play_failure_after_score_change_includes_latest_known_state() -> None:
    client = FakeClient()
    client.play_error = McpToolError.create(
        ErrorCode.BACKEND_UNAVAILABLE,
        "DrumNext 服务当前不可用",
        retryable=True,
    )

    with pytest.raises(McpToolError) as captured:
        await make_tools(client).play("second")

    assert client.calls == [
        ("list_scores", None),
        ("change_score", "second"),
        ("play", None),
    ]
    assert captured.value.payload.details["playback"]["scoreId"] == "second"
    assert captured.value.payload.details["playback"]["status"] == "stopped"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("seconds", "milliseconds"), [(0, 0.0), (2, 2000.0), (1.2345, 1234.5)]
)
async def test_seek_converts_seconds_to_milliseconds(
    seconds: int | float, milliseconds: float
) -> None:
    client = FakeClient()

    await make_tools(client).seek(seconds)

    assert client.calls == [("seek", milliseconds)]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("operation", "value"),
    [
        ("seek", -1),
        ("seek", True),
        ("seek", float("inf")),
        ("set_speed", 0.24),
        ("set_speed", 4.01),
        ("set_speed", "1"),
        ("play", ""),
        ("play", "x" * 65),
    ],
)
async def test_invalid_arguments_use_stable_error(operation: str, value: Any) -> None:
    tools = make_tools(FakeClient())

    with pytest.raises(McpToolError) as captured:
        await getattr(tools, operation)(value)

    assert captured.value.payload.code == ErrorCode.INVALID_ARGUMENT
    assert captured.value.payload.retryable is False


@pytest.mark.anyio
async def test_tools_list_contains_exact_names_and_schemas() -> None:
    client = FakeClient()
    server = create_server(client, 100)  # type: ignore[arg-type]

    listed = await server.list_tools()
    by_name = {tool.name: tool for tool in listed}

    assert set(by_name) == {
        "drumnext_get_status",
        "drumnext_list_scores",
        "drumnext_play",
        "drumnext_pause",
        "drumnext_resume",
        "drumnext_stop",
        "drumnext_seek",
        "drumnext_set_speed",
    }
    play_schema = by_name["drumnext_play"].inputSchema
    assert "score_id" not in play_schema.get("required", [])
    assert play_schema["properties"]["score_id"]["anyOf"][0] == {
        "type": "string",
        "minLength": 1,
        "maxLength": 64,
    }
    seek_schema = by_name["drumnext_seek"].inputSchema
    assert seek_schema["required"] == ["position_seconds"]
    assert seek_schema["properties"]["position_seconds"]["minimum"] == 0
    speed_schema = by_name["drumnext_set_speed"].inputSchema
    assert speed_schema["properties"]["speed"]["minimum"] == 0.25
    assert speed_schema["properties"]["speed"]["maximum"] == 4.0
    assert by_name["drumnext_play"].title == "播放空灵鼓投影乐谱"
    assert all("空灵鼓" in (tool.title or "") for tool in listed)
    assert all("空灵鼓" in (tool.description or "") for tool in listed)


@pytest.mark.anyio
async def test_rest_error_is_an_mcp_tool_error_result() -> None:
    client = FakeClient()
    client.play_error = McpToolError.create(
        ErrorCode.BACKEND_UNAVAILABLE,
        "DrumNext 服务当前不可用",
        retryable=True,
    )
    server = create_server(client, 100)  # type: ignore[arg-type]

    result = await server.call_tool("drumnext_play", {})

    assert result.isError is True
    payload = json.loads(result.content[0].text)  # type: ignore[union-attr]
    assert payload == {
        "code": "BACKEND_UNAVAILABLE",
        "message": "DrumNext 服务当前不可用",
        "retryable": True,
        "details": {},
    }
