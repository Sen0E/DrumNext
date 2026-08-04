import asyncio
from collections.abc import Callable

from fastapi import WebSocket

from drumnext.domain.protocol import EventEnvelope, PlaybackSnapshot
from drumnext.playback.clock import MonotonicClock


class EventHub:
    def __init__(self, clock: MonotonicClock) -> None:
        self._clock = clock
        self._sequence = 0
        self._connections: set[WebSocket] = set()
        self._send_locks: dict[WebSocket, asyncio.Lock] = {}
        self._sequence_lock = asyncio.Lock()

    async def envelope(self, event_type: str, payload: dict[str, object]) -> EventEnvelope:
        async with self._sequence_lock:
            self._sequence += 1
            return EventEnvelope(
                type=event_type,
                sequence=self._sequence,
                serverTimeMs=self._clock.now_ms(),
                payload=payload,
            )

    async def connect(self, websocket: WebSocket, snapshot: PlaybackSnapshot) -> None:
        await websocket.accept()
        self._send_locks[websocket] = asyncio.Lock()
        message = await self.envelope(
            "playback.snapshot", snapshot.model_dump(by_alias=True, mode="json")
        )
        await self.send(websocket, message)
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)
        self._send_locks.pop(websocket, None)

    async def send(self, websocket: WebSocket, message: EventEnvelope) -> None:
        lock = self._send_locks.get(websocket)
        if lock is None:
            return
        async with lock:
            await websocket.send_json(message.model_dump(by_alias=True, mode="json"))

    async def broadcast_snapshot(self, event_type: str, snapshot: PlaybackSnapshot) -> None:
        message = await self.envelope(
            event_type, snapshot.model_dump(by_alias=True, mode="json")
        )
        await self.broadcast(message)

    async def broadcast(self, message: EventEnvelope) -> None:
        dead: list[WebSocket] = []
        for websocket in tuple(self._connections):
            try:
                await self.send(websocket, message)
            except RuntimeError:
                dead.append(websocket)
        for websocket in dead:
            self.disconnect(websocket)


EventPublisher = Callable[[str, PlaybackSnapshot], object]
