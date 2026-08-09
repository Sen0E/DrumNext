from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import anyio
import httpx
import pytest
from mcp import ClientSession
from mcp.shared.message import SessionMessage

from drumnext_mcp.api_client import DrumNextApiClient
from drumnext_mcp.config import DrumNextConfig
from drumnext_mcp.server import create_server

PROJECT_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = PROJECT_ROOT / "shared" / "fixtures" / "mcp"


def playback_payload(**updates: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "playing",
        "scoreId": "fish",
        "durationMs": 168_154,
        "positionMs": 0,
        "anchorPositionMs": 0,
        "anchorClockMs": 12_500.2,
        "speed": 1.0,
    }
    payload.update(updates)
    return payload


@pytest.mark.anyio
async def test_initialize_list_and_call_over_mcp_session() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/v1/scores":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "fish",
                        "title": "大鱼",
                        "durationMs": 168_154,
                        "noteCount": 100,
                    }
                ],
            )
        if request.url.path == "/api/v1/playback/score":
            return httpx.Response(200, json=playback_payload(status="stopped"))
        return httpx.Response(200, json=playback_payload())

    config = DrumNextConfig.model_validate(
        {"baseUrl": "http://backend.test", "requestTimeoutSeconds": 5}
    )
    async with DrumNextApiClient(
        config.base_url,
        config.request_timeout_seconds,
        transport=httpx.MockTransport(handler),
    ) as api_client:
        server = create_server(api_client, 100)
        client_send, server_receive = anyio.create_memory_object_stream[
            SessionMessage | Exception
        ](0)
        server_send, client_receive = anyio.create_memory_object_stream[SessionMessage](0)

        async with (
            client_send,
            server_receive,
            server_send,
            client_receive,
            anyio.create_task_group() as task_group,
        ):
            task_group.start_soon(
                server._mcp_server.run,
                server_receive,
                server_send,
                server._mcp_server.create_initialization_options(),
            )
            async with ClientSession(client_receive, client_send) as session:
                initialized = await session.initialize()
                listed = await session.list_tools()
                called = await session.call_tool("drumnext_play", {"score_id": "大鱼"})
            task_group.cancel_scope.cancel()

    assert initialized.serverInfo.name == "DrumNext 空灵鼓投影"
    assert "空灵鼓演奏引导投影" in (initialized.instructions or "")
    assert initialized.capabilities.tools is not None
    assert initialized.capabilities.resources is None
    assert initialized.capabilities.prompts is None
    assert len(listed.tools) == 8
    assert called.isError is False
    assert called.structuredContent["message"] == "空灵鼓投影已开始播放乐谱《大鱼》"
    assert called.structuredContent["playback"]["scoreId"] == "fish"
    assert [(request.method, request.url.path) for request in requests] == [
        ("GET", "/api/v1/scores"),
        ("POST", "/api/v1/playback/score"),
        ("POST", "/api/v1/playback/play"),
    ]


def test_protocol_fixtures_are_valid_json_rpc_requests() -> None:
    fixtures = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(FIXTURES.glob("*.json"))
    ]

    assert len(fixtures) == 3
    assert all(fixture["jsonrpc"] == "2.0" for fixture in fixtures)
    assert {fixture["method"] for fixture in fixtures} == {
        "initialize",
        "tools/list",
        "tools/call",
    }


def test_server_source_cannot_pollute_stdout_with_prints() -> None:
    source_path = PROJECT_ROOT / "backend" / "drumnext_mcp" / "server.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))

    print_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "print"
    ]
    assert print_calls == []
