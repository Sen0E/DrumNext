from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from drumnext.config import Settings
from drumnext.main import create_app


@pytest.mark.anyio
async def test_health_returns_stable_versioned_response(tmp_path: Path) -> None:
    app = create_app(Settings(projection_dist=tmp_path))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


@pytest.mark.anyio
async def test_unbuilt_projection_has_diagnostic_response(tmp_path: Path) -> None:
    app = create_app(Settings(projection_dist=tmp_path))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")

    assert response.status_code == 503
    assert "投影页面尚未构建" in response.text


@pytest.mark.anyio
async def test_fastapi_hosts_api_debug_page(tmp_path: Path) -> None:
    app = create_app(Settings(projection_dist=tmp_path))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/debug/api")

    assert response.status_code == 200
    assert "DrumNext API 调试" in response.text
    assert "/api/v1/playback/play" not in response.text
