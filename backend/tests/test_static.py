from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from drumnext.config import Settings
from drumnext.main import create_app


@pytest.mark.anyio
async def test_built_projection_is_served_with_spa_fallback(tmp_path: Path) -> None:
    index = tmp_path / "index.html"
    index.write_text("<h1>projection</h1>", encoding="utf-8")
    app = create_app(Settings(projection_dist=tmp_path))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        root_response = await client.get("/")
        route_response = await client.get("/projection/debug")

    assert root_response.status_code == 200
    assert route_response.status_code == 200
    assert route_response.text == "<h1>projection</h1>"


@pytest.mark.anyio
async def test_static_route_does_not_escape_distribution(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("safe", encoding="utf-8")
    outside = tmp_path.parent / "secret.txt"
    outside.write_text("secret", encoding="utf-8")
    app = create_app(Settings(projection_dist=tmp_path))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/../secret.txt")

    assert response.text != "secret"
