import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from drumnext.config import Settings
from drumnext.main import create_app


@pytest.mark.anyio
async def test_ending_animation_defaults_to_calm_and_persists_updates(
    tmp_path: Path,
) -> None:
    settings_path = tmp_path / "ending-animation.json"
    settings = Settings(
        projection_dist=tmp_path / "dist",
        ending_animation_file=settings_path,
    )
    app = create_app(settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        initial = await client.get("/api/v1/settings/ending-animation")
        updated = await client.put(
            "/api/v1/settings/ending-animation", json={"style": "spectacular"}
        )

    assert initial.json() == {"style": "calm"}
    assert updated.json() == {"style": "spectacular"}
    assert json.loads(settings_path.read_text(encoding="utf-8")) == {
        "style": "spectacular"
    }

    restarted_app = create_app(settings)
    async with AsyncClient(
        transport=ASGITransport(app=restarted_app), base_url="http://test"
    ) as client:
        persisted = await client.get("/api/v1/settings/ending-animation")

    assert persisted.json() == {"style": "spectacular"}


@pytest.mark.anyio
async def test_ending_animation_rejects_unknown_style(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            projection_dist=tmp_path / "dist",
            ending_animation_file=tmp_path / "ending-animation.json",
        )
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put(
            "/api/v1/settings/ending-animation", json={"style": "unknown"}
        )

    assert response.status_code == 422
    assert not (tmp_path / "ending-animation.json").exists()
