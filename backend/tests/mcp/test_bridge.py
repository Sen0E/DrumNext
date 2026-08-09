from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from pydantic import WebsocketUrl

import drumnext_mcp.bridge as bridge_module
from drumnext_mcp.bridge import (
    BridgeProtocolError,
    BridgeService,
    _spawn_server,
    calculate_reconnect_delay,
    cleanup_process,
    forward_stderr_to_log,
    forward_stdout_to_websocket,
    forward_websocket_to_stdin,
    run_bridge_session,
)
from drumnext_mcp.config import (
    EndpointConfig,
    McpConfig,
    ProcessConfig,
    ReconnectConfig,
    load_config,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
EXAMPLE_CONFIG = PROJECT_ROOT / "config" / "xiaozhi-mcp.example.json"


@pytest.fixture
def config() -> McpConfig:
    loaded = load_config(EXAMPLE_CONFIG)
    return loaded.model_copy(
        update={
            "process": ProcessConfig.model_construct(
                shutdown_grace_seconds=0.001,
                terminate_grace_seconds=0.001,
            )
        }
    )


class FakeWriter:
    def __init__(self, events: list[str] | None = None) -> None:
        self.data = bytearray()
        self.drain_count = 0
        self.closed = False
        self._events = events

    def write(self, data: bytes) -> None:
        self.data.extend(data)
        if self._events is not None:
            self._events.append("write")

    async def drain(self) -> None:
        self.drain_count += 1
        if self._events is not None:
            self._events.append("drain")

    def close(self) -> None:
        self.closed = True
        if self._events is not None:
            self._events.append("close_stdin")

    def is_closing(self) -> bool:
        return self.closed

    async def wait_closed(self) -> None:
        if self._events is not None:
            self._events.append("wait_closed")


class FakeWebSocket:
    def __init__(self, messages: list[str | bytes] | None = None) -> None:
        self.messages = list(messages or [])
        self.sent: list[str] = []
        self.closed: list[tuple[int, str]] = []
        self.wait_forever = asyncio.Event()

    async def recv(self, decode: bool | None = None) -> str | bytes:
        del decode
        if self.messages:
            return self.messages.pop(0)
        await self.wait_forever.wait()
        raise AssertionError("unreachable")

    async def send(self, message: str) -> None:
        self.sent.append(message)

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed.append((code, reason))


def reader_with(data: bytes, *, eof: bool = True) -> asyncio.StreamReader:
    reader = asyncio.StreamReader()
    reader.feed_data(data)
    if eof:
        reader.feed_eof()
    return reader


class FakeProcess:
    def __init__(
        self,
        *,
        stdout: bytes = b"",
        stderr: bytes = b"",
        events: list[str] | None = None,
    ) -> None:
        self.events = events if events is not None else []
        self.stdin = FakeWriter(self.events)
        self.stdout = reader_with(stdout)
        self.stderr = reader_with(stderr)
        self.returncode: int | None = None
        self.pid = 123
        self._killed = asyncio.Event()

    async def wait(self) -> int:
        self.events.append("wait")
        if self.returncode is None:
            await self._killed.wait()
        assert self.returncode is not None
        return self.returncode

    def terminate(self) -> None:
        self.events.append("terminate")

    def kill(self) -> None:
        self.events.append("kill")
        self.returncode = -9
        self._killed.set()


async def cancel_after_first_write(
    operation: Awaitable[None], writer: FakeWriter
) -> None:
    task = asyncio.create_task(operation)
    for _ in range(20):
        if writer.drain_count:
            break
        await asyncio.sleep(0)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "message",
    [
        '{"jsonrpc":"2.0","id":1,"method":"tools/list"}',
        '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"标题":"大鱼"}}',
    ],
)
async def test_websocket_message_is_written_to_stdin_and_flushed(message: str) -> None:
    websocket = FakeWebSocket([message])
    process = FakeProcess()

    await cancel_after_first_write(
        forward_websocket_to_stdin(websocket, process, 1_048_576), process.stdin
    )

    assert bytes(process.stdin.data) == message.encode() + b"\n"
    assert process.stdin.drain_count == 1


@pytest.mark.anyio
async def test_valid_utf8_binary_message_is_accepted() -> None:
    message = b'{"jsonrpc":"2.0","id":1}'
    websocket = FakeWebSocket([message])
    process = FakeProcess()

    await cancel_after_first_write(
        forward_websocket_to_stdin(websocket, process, 1024), process.stdin
    )

    assert bytes(process.stdin.data) == message + b"\n"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("message", "close_code"),
    [(b"\xff", 1007), ("x" * 1025, 1009)],
)
async def test_invalid_or_oversized_websocket_message_ends_session(
    message: str | bytes, close_code: int
) -> None:
    websocket = FakeWebSocket([message])
    process = FakeProcess()

    with pytest.raises(BridgeProtocolError) as captured:
        await forward_websocket_to_stdin(websocket, process, 1024)

    assert captured.value.close_code == close_code
    assert process.stdin.data == b""


@pytest.mark.anyio
async def test_stdout_line_is_sent_as_unchanged_text_frame() -> None:
    message = '{"jsonrpc":"2.0","id":1,"result":{"ok":true}}'
    websocket = FakeWebSocket()
    process = FakeProcess(stdout=(message + "\r\n").encode())

    await forward_stdout_to_websocket(process, websocket, 1024)

    assert websocket.sent == [message]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "stdout",
    [
        b"application log pollution\n",
        b'{"ordinary":"json"}\n',
        b'{"jsonrpc":"2.0"',
    ],
)
async def test_invalid_stdout_is_a_protocol_error(stdout: bytes) -> None:
    websocket = FakeWebSocket()
    process = FakeProcess(stdout=stdout)

    with pytest.raises(BridgeProtocolError):
        await forward_stdout_to_websocket(process, websocket, 1024)

    assert websocket.sent == []


@pytest.mark.anyio
async def test_oversized_stdout_is_rejected() -> None:
    websocket = FakeWebSocket()
    process = FakeProcess(stdout=b"{" + b"x" * 1024 + b"}\n")

    with pytest.raises(BridgeProtocolError) as captured:
        await forward_stdout_to_websocket(process, websocket, 1024)

    assert captured.value.close_code == 1009


@pytest.mark.anyio
async def test_stderr_only_goes_to_service_log(caplog: pytest.LogCaptureFixture) -> None:
    process = FakeProcess(stderr="child diagnostic\n第二行\n".encode())

    with caplog.at_level("INFO", logger="drumnext_mcp.bridge"):
        await forward_stderr_to_log(process)

    assert "child diagnostic" in caplog.text
    assert "第二行" in caplog.text


@pytest.mark.anyio
async def test_cleanup_order_is_close_terminate_then_kill() -> None:
    events: list[str] = []
    process = FakeProcess(events=events)

    await cleanup_process(process, 0.001, 0.001)

    assert events[0:2] == ["close_stdin", "wait_closed"]
    assert events.count("wait") == 3
    assert events.index("terminate") > events.index("wait")
    assert events.index("kill") > events.index("terminate")
    assert process.returncode == -9


@pytest.mark.anyio
async def test_protocol_error_closes_websocket_and_reaps_child(config: McpConfig) -> None:
    websocket = FakeWebSocket()
    process = FakeProcess(stdout=b"not-json\n")

    async def spawn(_config: McpConfig) -> FakeProcess:
        return process

    with pytest.raises(BridgeProtocolError):
        await run_bridge_session(websocket, config, spawn)  # type: ignore[arg-type]

    assert websocket.closed == [(1002, "MCP protocol error")]
    assert process.returncode == -9


@pytest.mark.anyio
async def test_every_session_gets_a_new_process_without_replay(config: McpConfig) -> None:
    processes: list[FakeProcess] = []

    async def spawn(_config: McpConfig) -> FakeProcess:
        process = FakeProcess(stdout=b"")
        processes.append(process)
        return process

    await run_bridge_session(FakeWebSocket(), config, spawn)  # type: ignore[arg-type]
    await run_bridge_session(FakeWebSocket(), config, spawn)  # type: ignore[arg-type]

    assert len(processes) == 2
    assert processes[0] is not processes[1]
    assert processes[0].stdin.data == b""
    assert processes[1].stdin.data == b""
    assert all(process.returncode == -9 for process in processes)


@pytest.mark.anyio
async def test_cancellation_reaps_child_without_leaving_a_zombie(config: McpConfig) -> None:
    process = FakeProcess()
    process.stdout = reader_with(b"", eof=False)
    process.stderr = reader_with(b"", eof=False)
    spawned = asyncio.Event()

    async def spawn(_config: McpConfig) -> FakeProcess:
        spawned.set()
        return process

    task = asyncio.create_task(
        run_bridge_session(FakeWebSocket(), config, spawn)  # type: ignore[arg-type]
    )
    await spawned.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert process.returncode == -9
    assert "kill" in process.events


@pytest.mark.anyio
async def test_stable_session_resets_failure_count_with_fake_clock(
    config: McpConfig,
) -> None:
    reconnect = ReconnectConfig.model_construct(
        initial_delay_seconds=1,
        max_delay_seconds=60,
        multiplier=2,
        jitter_ratio=0,
        stable_reset_seconds=30,
    )
    config = config.model_copy(update={"reconnect": reconnect})
    clock_values = iter([0.0, 1.0, 2.0, 3.0, 4.0, 40.0])
    delays: list[float] = []
    stop_event = asyncio.Event()

    @asynccontextmanager
    async def connection_factory(_config: McpConfig):
        yield FakeWebSocket()

    async def spawn(_config: McpConfig) -> FakeProcess:
        return FakeProcess(stdout=b"")

    async def record_wait(_stop_event: asyncio.Event, delay: float) -> bool:
        delays.append(delay)
        if len(delays) == 3:
            stop_event.set()
        return stop_event.is_set()

    service = BridgeService(
        config,
        connection_factory=connection_factory,
        process_factory=spawn,  # type: ignore[arg-type]
        monotonic=lambda: next(clock_values),
        uniform=lambda _low, _high: 0,
        reconnect_waiter=record_wait,
    )

    await service.run_forever(stop_event)

    assert delays == [1, 2, 1]


@pytest.mark.anyio
async def test_connection_logs_never_include_endpoint_secret(
    config: McpConfig, caplog: pytest.LogCaptureFixture
) -> None:
    secret = "wss-secret-token"
    endpoint = config.endpoint.model_copy(
        update={"url": WebsocketUrl(f"wss://example.test/private?token={secret}")}
    )
    config = config.model_copy(update={"endpoint": endpoint})
    stop_event = asyncio.Event()

    @asynccontextmanager
    async def failing_connection(_config: McpConfig):
        if False:  # pragma: no cover - keeps this an async generator
            yield FakeWebSocket()
        raise OSError(f"connection failed for {secret}")

    async def stop_after_failure(_stop_event: asyncio.Event, _delay: float) -> bool:
        stop_event.set()
        return True

    service = BridgeService(
        config,
        connection_factory=failing_connection,
        reconnect_waiter=stop_after_failure,
    )
    with caplog.at_level("INFO", logger="drumnext_mcp.bridge"):
        await service.run_forever(stop_event)

    assert secret not in caplog.text
    assert "/private" not in caplog.text
    assert "OSError" in caplog.text


@pytest.mark.anyio
async def test_authentication_failure_uses_low_frequency_retry(
    config: McpConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    stop_event = asyncio.Event()
    delays: list[float] = []

    @asynccontextmanager
    async def failing_connection(_config: McpConfig):
        if False:  # pragma: no cover - keeps this an async generator
            yield FakeWebSocket()
        raise PermissionError("authentication rejected")

    async def record_wait(_stop_event: asyncio.Event, delay: float) -> bool:
        delays.append(delay)
        stop_event.set()
        return True

    monkeypatch.setattr(
        bridge_module, "_is_authentication_failure", lambda _error: True
    )
    service = BridgeService(
        config,
        connection_factory=failing_connection,
        reconnect_waiter=record_wait,
    )

    await service.run_forever(stop_event)

    assert delays == [config.reconnect.max_delay_seconds]


@pytest.mark.anyio
async def test_child_process_arguments_do_not_include_endpoint(
    config: McpConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = "child-must-not-see-this"
    endpoint: EndpointConfig = config.endpoint.model_copy(
        update={"url": WebsocketUrl(f"wss://example.test/mcp?token={secret}")}
    )
    config = config.model_copy(update={"endpoint": endpoint})
    captured: dict[str, object] = {}
    process = FakeProcess()

    async def fake_subprocess(*args: object, **kwargs: object) -> FakeProcess:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_subprocess)

    assert await _spawn_server(config) is process
    serialized = json.dumps(captured, default=str)
    assert secret not in serialized
    assert str(config.endpoint.url) not in serialized
    assert "--base-url" in serialized
    assert "drumnext_mcp.server" in serialized


def test_reconnect_backoff_has_multiplier_cap_and_jitter(config: McpConfig) -> None:
    assert [
        calculate_reconnect_delay(failure, config, uniform=lambda _low, _high: 0)
        for failure in range(8)
    ] == [1, 2, 4, 8, 16, 32, 60, 60]
    assert calculate_reconnect_delay(0, config, uniform=lambda _low, _high: -0.2) == 0.8
    assert calculate_reconnect_delay(0, config, uniform=lambda _low, _high: 0.2) == 1.2
    assert calculate_reconnect_delay(8, config, uniform=lambda _low, _high: 0.2) == 60
    assert calculate_reconnect_delay(100_000, config, uniform=lambda _low, _high: 0) == 60


def test_example_messages_remain_valid_json() -> None:
    for path in (PROJECT_ROOT / "shared" / "fixtures" / "mcp").glob("*.json"):
        assert isinstance(json.loads(path.read_text(encoding="utf-8")), dict)
