from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from drumnext_mcp.api_client import DrumNextApiClient
from drumnext_mcp.config import DrumNextConfig
from drumnext_mcp.errors import ErrorCode, McpToolError


def playback_payload(**updates: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "playing",
        "scoreId": "demo",
        "durationMs": 10_000,
        "positionMs": 500,
        "anchorPositionMs": 500,
        "anchorClockMs": 12_500.2,
        "speed": 1.0,
    }
    payload.update(updates)
    return payload


def make_client(handler: Callable[[httpx.Request], httpx.Response]) -> DrumNextApiClient:
    config = DrumNextConfig.model_validate(
        {"baseUrl": "http://backend.test", "requestTimeoutSeconds": 5}
    )
    return DrumNextApiClient(
        config.base_url,
        config.request_timeout_seconds,
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.anyio
async def test_each_method_uses_only_the_fixed_method_path_and_body() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/v1/scores":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "demo",
                        "title": "示例",
                        "durationMs": 10_000,
                        "noteCount": 8,
                    }
                ],
            )
        return httpx.Response(200, json=playback_payload())

    async with make_client(handler) as client:
        await client.get_status()
        await client.list_scores()
        await client.play()
        await client.pause()
        await client.resume()
        await client.stop()
        await client.seek(1250.5)
        await client.set_speed(1.5)
        await client.change_score("demo")

    assert [(request.method, request.url.path) for request in requests] == [
        ("GET", "/api/v1/playback"),
        ("GET", "/api/v1/scores"),
        ("POST", "/api/v1/playback/play"),
        ("POST", "/api/v1/playback/pause"),
        ("POST", "/api/v1/playback/resume"),
        ("POST", "/api/v1/playback/stop"),
        ("POST", "/api/v1/playback/seek"),
        ("POST", "/api/v1/playback/speed"),
        ("POST", "/api/v1/playback/score"),
    ]
    assert json.loads(requests[6].content) == {"positionMs": 1250.5}
    assert json.loads(requests[7].content) == {"speed": 1.5}
    assert json.loads(requests[8].content) == {"scoreId": "demo"}


@pytest.mark.anyio
async def test_response_models_ignore_new_fields_but_require_documented_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/scores":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "demo",
                        "title": "示例",
                        "durationMs": 10_000,
                        "noteCount": 8,
                        "futureField": True,
                        "notes": [{"secret": "not returned"}],
                    }
                ],
            )
        return httpx.Response(200, json=playback_payload(futureField=True))

    async with make_client(handler) as client:
        playback = await client.get_status()
        scores = await client.list_scores()

    assert "futureField" not in playback.model_dump()
    assert scores[0].model_dump(mode="json", by_alias=True) == {
        "id": "demo",
        "title": "示例",
        "durationMs": 10_000,
        "noteCount": 8,
    }


@pytest.mark.anyio
@pytest.mark.parametrize("exception_type", [httpx.ConnectError, httpx.ReadTimeout])
async def test_connection_and_timeout_map_to_backend_unavailable(
    exception_type: type[httpx.RequestError],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise exception_type("private failure text", request=request)

    async with make_client(handler) as client:
        with pytest.raises(McpToolError) as captured:
            await client.get_status()

    assert captured.value.payload.code == ErrorCode.BACKEND_UNAVAILABLE
    assert captured.value.payload.retryable is True
    assert "private failure text" not in captured.value.as_json()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status", "code", "retryable"),
    [
        (404, ErrorCode.BACKEND_REJECTED, False),
        (422, ErrorCode.BACKEND_REJECTED, False),
        (429, ErrorCode.BACKEND_REJECTED, True),
        (500, ErrorCode.BACKEND_FAILURE, True),
    ],
)
async def test_http_statuses_map_without_exposing_response_body(
    status: int, code: ErrorCode, retryable: bool
) -> None:
    async with make_client(
        lambda _request: httpx.Response(status, text="<html>private stack</html>")
    ) as client:
        with pytest.raises(McpToolError) as captured:
            await client.get_status()

    assert captured.value.payload.code == code
    assert captured.value.payload.retryable is retryable
    assert captured.value.payload.details == {"statusCode": status}
    assert "private stack" not in captured.value.as_json()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, content=b"not-json"),
        httpx.Response(200, json={"status": "playing"}),
    ],
)
async def test_invalid_json_or_dto_maps_to_backend_failure(response: httpx.Response) -> None:
    async with make_client(lambda _request: response) as client:
        with pytest.raises(McpToolError) as captured:
            await client.get_status()

    assert captured.value.payload.code == ErrorCode.BACKEND_FAILURE
    assert captured.value.payload.retryable is True


@pytest.mark.anyio
async def test_tool_value_cannot_change_target_host_or_path() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=playback_payload())

    async with make_client(handler) as client:
        await client.change_score("https://attacker.test/private")

    assert requests[0].url.host == "backend.test"
    assert requests[0].url.path == "/api/v1/playback/score"
    assert json.loads(requests[0].content) == {
        "scoreId": "https://attacker.test/private"
    }
