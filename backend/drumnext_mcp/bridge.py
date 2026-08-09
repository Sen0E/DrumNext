from __future__ import annotations

import argparse
import asyncio
import json
import logging
import random
import signal
import sys
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import AbstractAsyncContextManager, suppress
from pathlib import Path
from typing import Protocol

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosedOK, InvalidStatus

from drumnext_mcp.config import ConfigError, McpConfig, load_config

logger = logging.getLogger(__name__)
websocket_logger = logging.getLogger("drumnext_mcp.websocket_transport")
websocket_logger.addHandler(logging.NullHandler())
websocket_logger.propagate = False
websocket_logger.setLevel(logging.CRITICAL + 1)


class WebSocketLike(Protocol):
    async def recv(self, decode: bool | None = None) -> str | bytes: ...

    async def send(self, message: str) -> None: ...

    async def close(self, code: int = 1000, reason: str = "") -> None: ...


class ProcessLike(Protocol):
    stdin: asyncio.StreamWriter | None
    stdout: asyncio.StreamReader | None
    stderr: asyncio.StreamReader | None
    returncode: int | None

    async def wait(self) -> int: ...

    def terminate(self) -> None: ...

    def kill(self) -> None: ...


ProcessFactory = Callable[[McpConfig], Awaitable[ProcessLike]]
ConnectionFactory = Callable[[McpConfig], AbstractAsyncContextManager[WebSocketLike]]
BridgeRunner = Callable[[McpConfig], Awaitable[None]]
ReconnectWaiter = Callable[[asyncio.Event, float], Awaitable[bool]]


class BridgeProtocolError(Exception):
    def __init__(self, message: str, *, close_code: int = 1002) -> None:
        self.close_code = close_code
        super().__init__(message)


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class BridgeService:
    def __init__(
        self,
        config: McpConfig,
        *,
        connection_factory: ConnectionFactory | None = None,
        process_factory: ProcessFactory | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        uniform: Callable[[float, float], float] = random.uniform,
        reconnect_waiter: ReconnectWaiter | None = None,
    ) -> None:
        self._config = config
        self._connection_factory = connection_factory or _connect_websocket
        self._process_factory = process_factory or _spawn_server
        self._monotonic = monotonic
        self._uniform = uniform
        self._reconnect_waiter = reconnect_waiter or _wait_for_stop

    async def run_forever(self, stop_event: asyncio.Event) -> None:
        failures = 0
        while not stop_event.is_set():
            connected_at: float | None = None
            auth_failure = False
            try:
                async with self._connection_factory(self._config) as websocket:
                    connected_at = self._monotonic()
                    logger.info(
                        "WSS connected endpoint=%s",
                        self._config.redacted_log_view()["endpoint"]["url"],
                    )
                    await self._run_session_until_stopped(websocket, stop_event)
                    logger.info(
                        "WSS session ended close_code=%s",
                        getattr(websocket, "close_code", None),
                    )
            except asyncio.CancelledError:
                raise
            except Exception as error:
                auth_failure = _is_authentication_failure(error)
                _log_connection_end(error)

            if stop_event.is_set():
                return

            if (
                connected_at is not None
                and self._monotonic() - connected_at
                >= self._config.reconnect.stable_reset_seconds
            ):
                failures = 0

            delay = (
                self._config.reconnect.max_delay_seconds
                if auth_failure
                else calculate_reconnect_delay(
                    failures,
                    self._config,
                    uniform=self._uniform,
                )
            )
            failures += 1
            logger.warning("WSS reconnect attempt=%d delay_seconds=%.3f", failures, delay)
            if await self._reconnect_waiter(stop_event, delay):
                return

    async def _run_session_until_stopped(
        self, websocket: WebSocketLike, stop_event: asyncio.Event
    ) -> None:
        session_task = asyncio.create_task(
            run_bridge_session(websocket, self._config, self._process_factory),
            name="mcp-bridge-session",
        )
        stop_task = asyncio.create_task(stop_event.wait(), name="mcp-stop-wait")
        done, _ = await asyncio.wait(
            {session_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
        )
        if stop_task in done:
            session_task.cancel()
            await asyncio.gather(session_task, return_exceptions=True)
            return

        stop_task.cancel()
        await asyncio.gather(stop_task, return_exceptions=True)
        await session_task


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="drumnext-mcp")
    parser.add_argument(
        "--config",
        type=Path,
        help="MCP JSON configuration path (defaults to config/xiaozhi-mcp.json)",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    bridge_runner: BridgeRunner | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as error:
        print(f"drumnext-mcp: configuration error: {error}", file=sys.stderr)
        return 2

    _configure_logging(config)
    logger.info(
        "MCP service starting schema_version=%d config=%s endpoint=%s",
        config.schema_version,
        args.config or "config/xiaozhi-mcp.json",
        config.redacted_log_view()["endpoint"]["url"],
    )
    try:
        asyncio.run((bridge_runner or run_bridge)(config))
    except KeyboardInterrupt:
        logger.info("MCP service interrupted")
    return 0


async def run_bridge(config: McpConfig) -> None:
    stop_event = asyncio.Event()
    service = BridgeService(config)
    current_task = asyncio.current_task()
    loop = asyncio.get_running_loop()
    installed_signals: list[signal.Signals] = []

    def request_stop() -> None:
        stop_event.set()
        if (
            current_task is not None
            and not current_task.done()
            and current_task.cancelling() == 0
        ):
            current_task.cancel()

    for handled_signal in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(handled_signal, request_stop)
            installed_signals.append(handled_signal)
        except (NotImplementedError, RuntimeError):  # pragma: no cover - platform dependent
            pass

    try:
        await service.run_forever(stop_event)
    except asyncio.CancelledError:
        if not stop_event.is_set():
            raise
    finally:
        for handled_signal in installed_signals:
            loop.remove_signal_handler(handled_signal)


async def run_bridge_session(
    websocket: WebSocketLike,
    config: McpConfig,
    process_factory: ProcessFactory | None = None,
) -> None:
    factory = process_factory or _spawn_server
    process = await factory(config)
    logger.info("MCP child started pid=%s", getattr(process, "pid", "unknown"))
    websocket_to_stdin = asyncio.create_task(
        forward_websocket_to_stdin(
            websocket, process, config.limits.max_message_bytes
        ),
        name="wss-to-mcp-stdin",
    )
    stdout_to_websocket = asyncio.create_task(
        forward_stdout_to_websocket(
            process, websocket, config.limits.max_message_bytes
        ),
        name="mcp-stdout-to-wss",
    )
    stderr_to_log = asyncio.create_task(
        forward_stderr_to_log(process), name="mcp-stderr-to-log"
    )
    process_exit = asyncio.create_task(process.wait(), name="mcp-child-wait")
    tasks = {
        websocket_to_stdin,
        stdout_to_websocket,
        stderr_to_log,
        process_exit,
    }
    try:
        done, _ = await asyncio.wait(
            {websocket_to_stdin, stdout_to_websocket, process_exit},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in done:
            if task.cancelled():
                continue
            error = task.exception()
            if error is not None:
                raise error
    except BridgeProtocolError as error:
        logger.warning("MCP session protocol error=%s", type(error).__name__)
        await websocket.close(code=error.close_code, reason="MCP protocol error")
        raise
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await cleanup_process(
            process,
            config.process.shutdown_grace_seconds,
            config.process.terminate_grace_seconds,
        )


async def forward_websocket_to_stdin(
    websocket: WebSocketLike,
    process: ProcessLike,
    max_message_bytes: int,
) -> None:
    if process.stdin is None:
        raise BridgeProtocolError("MCP child stdin is unavailable")
    while True:
        try:
            message = await websocket.recv()
        except ConnectionClosedOK:
            return
        if isinstance(message, bytes):
            if len(message) > max_message_bytes:
                raise BridgeProtocolError("WebSocket message is too large", close_code=1009)
            try:
                message = message.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                raise BridgeProtocolError(
                    "binary WebSocket message is not UTF-8", close_code=1007
                ) from None
        encoded = message.encode("utf-8")
        if len(encoded) > max_message_bytes:
            raise BridgeProtocolError("WebSocket message is too large", close_code=1009)
        try:
            process.stdin.write(encoded + b"\n")
            await process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            return


async def forward_stdout_to_websocket(
    process: ProcessLike,
    websocket: WebSocketLike,
    max_message_bytes: int,
) -> None:
    if process.stdout is None:
        raise BridgeProtocolError("MCP child stdout is unavailable")
    while True:
        try:
            line = await process.stdout.readline()
        except (ValueError, asyncio.LimitOverrunError):
            raise BridgeProtocolError("MCP stdout line is too large", close_code=1009) from None
        if not line:
            return
        if not line.endswith(b"\n"):
            raise BridgeProtocolError("MCP stdout ended with an incomplete line")
        payload = line[:-1]
        if payload.endswith(b"\r"):
            payload = payload[:-1]
        if len(payload) > max_message_bytes:
            raise BridgeProtocolError("MCP stdout line is too large", close_code=1009)
        try:
            text = payload.decode("utf-8", errors="strict")
            parsed = json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise BridgeProtocolError("MCP stdout contains invalid JSON") from None
        if not isinstance(parsed, dict) or parsed.get("jsonrpc") != "2.0":
            raise BridgeProtocolError("MCP stdout contains a non-JSON-RPC message")
        await websocket.send(text)


async def forward_stderr_to_log(process: ProcessLike) -> None:
    if process.stderr is None:
        return
    async for raw_line in _iterate_lines(process.stderr):
        logger.info("MCP child: %s", raw_line.decode("utf-8", errors="replace").rstrip())


async def _iterate_lines(reader: asyncio.StreamReader) -> AsyncIterator[bytes]:
    while line := await reader.readline():
        yield line


async def cleanup_process(
    process: ProcessLike,
    shutdown_grace_seconds: float,
    terminate_grace_seconds: float,
) -> None:
    if process.stdin is not None and not process.stdin.is_closing():
        process.stdin.close()
        with suppress(BrokenPipeError, ConnectionResetError):
            await process.stdin.wait_closed()

    if process.returncode is not None:
        await process.wait()
        logger.info("MCP child exited code=%s", process.returncode)
        return

    try:
        await asyncio.wait_for(process.wait(), timeout=shutdown_grace_seconds)
        logger.info("MCP child exited code=%s", process.returncode)
        return
    except TimeoutError:
        logger.warning("MCP child terminate")

    try:
        process.terminate()
    except ProcessLookupError:
        await process.wait()
        return
    try:
        await asyncio.wait_for(process.wait(), timeout=terminate_grace_seconds)
        logger.info("MCP child exited after terminate code=%s", process.returncode)
        return
    except TimeoutError:
        logger.warning("MCP child kill")

    try:
        process.kill()
    except ProcessLookupError:
        await process.wait()
        return
    await process.wait()
    logger.info("MCP child exited after kill code=%s", process.returncode)


def calculate_reconnect_delay(
    failures: int,
    config: McpConfig,
    *,
    uniform: Callable[[float, float], float] = random.uniform,
) -> float:
    reconnect = config.reconnect
    base = reconnect.initial_delay_seconds
    for _ in range(failures):
        base = min(reconnect.max_delay_seconds, base * reconnect.multiplier)
        if base >= reconnect.max_delay_seconds:
            break
    jitter = uniform(-reconnect.jitter_ratio, reconnect.jitter_ratio)
    return min(reconnect.max_delay_seconds, max(0.0, base * (1 + jitter)))


async def _wait_for_stop(stop_event: asyncio.Event, delay: float) -> bool:
    with suppress(TimeoutError):
        await asyncio.wait_for(stop_event.wait(), timeout=delay)
    return stop_event.is_set()


def _connect_websocket(config: McpConfig) -> AbstractAsyncContextManager[ClientConnection]:
    return connect(
        str(config.endpoint.url),
        open_timeout=config.endpoint.connect_timeout_seconds,
        ping_interval=config.endpoint.ping_interval_seconds,
        ping_timeout=config.endpoint.ping_timeout_seconds,
        close_timeout=config.endpoint.connect_timeout_seconds,
        max_size=config.limits.max_message_bytes,
        proxy=None,
        logger=websocket_logger,
    )


async def _spawn_server(config: McpConfig) -> ProcessLike:
    return await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "drumnext_mcp.server",
        "--base-url",
        str(config.drumnext.base_url),
        "--request-timeout-seconds",
        str(config.drumnext.request_timeout_seconds),
        "--max-scores-returned",
        str(config.limits.max_scores_returned),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        limit=config.limits.max_message_bytes + 2,
    )


def _is_authentication_failure(error: Exception) -> bool:
    return isinstance(error, InvalidStatus) and error.response.status_code in {401, 403}


def _log_connection_end(error: Exception) -> None:
    if isinstance(error, InvalidStatus):
        logger.warning(
            "WSS connection ended error=%s status=%d",
            type(error).__name__,
            error.response.status_code,
        )
        return
    close_code = getattr(getattr(error, "rcvd", None), "code", None)
    if close_code is not None:
        logger.warning(
            "WSS connection ended error=%s close_code=%s",
            type(error).__name__,
            close_code,
        )
        return
    logger.warning("WSS connection ended error=%s", type(error).__name__)


def _configure_logging(config: McpConfig) -> None:
    handler = logging.StreamHandler(sys.stderr)
    if config.logging.format == "json":
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(config.logging.level)


def run() -> None:
    raise SystemExit(main())
