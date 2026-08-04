from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from drumnext.config import Settings
from drumnext.main import create_app


@pytest.mark.anyio
async def test_playback_rest_commands_return_final_state(tmp_path: Path) -> None:
    app = create_app(Settings(projection_dist=tmp_path))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        started = await client.post("/api/v1/playback/play")
        paused = await client.post("/api/v1/playback/pause")
        speed = await client.post("/api/v1/playback/speed", json={"speed": 1.5})
        seeked = await client.post("/api/v1/playback/seek", json={"positionMs": 4_000})

    assert started.status_code == 200
    assert paused.json()["status"] == "paused"
    assert speed.json()["speed"] == 1.5
    assert seeked.json()["positionMs"] == 4_000


@pytest.mark.anyio
async def test_speed_validation_is_stable(tmp_path: Path) -> None:
    app = create_app(Settings(projection_dist=tmp_path))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/playback/speed", json={"speed": 10})

    assert response.status_code == 422
