import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from drumnext.config import Settings
from drumnext.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]


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


@pytest.mark.anyio
async def test_projection_visuals_default_and_persist_updates(tmp_path: Path) -> None:
    settings_path = tmp_path / "projection-visuals.json"
    settings = Settings(
        projection_dist=tmp_path / "dist",
        projection_visuals_file=settings_path,
    )
    app = create_app(settings)
    fixture_path = PROJECT_ROOT / "shared" / "fixtures" / "projection-visual-settings.json"
    expected_defaults = json.loads(fixture_path.read_text(encoding="utf-8"))
    updated_payload = {
        "showPerformanceInfo": True,
        "approachRingWidth": 18,
        "approachRingOpacity": 0.65,
        "lowPadScale": 1.1,
        "midPadScale": 0.95,
        "highPadScale": 1.2,
        "centerPadScale": 1.3,
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        initial = await client.get("/api/v1/settings/projection-visuals")
        updated = await client.put(
            "/api/v1/settings/projection-visuals", json=updated_payload
        )

    assert initial.json() == expected_defaults
    assert updated.json() == updated_payload
    assert json.loads(settings_path.read_text(encoding="utf-8")) == updated_payload

    restarted_app = create_app(settings)
    async with AsyncClient(
        transport=ASGITransport(app=restarted_app), base_url="http://test"
    ) as client:
        persisted = await client.get("/api/v1/settings/projection-visuals")

    assert persisted.json() == updated_payload


@pytest.mark.anyio
async def test_projection_visuals_reject_out_of_range_values(tmp_path: Path) -> None:
    settings_path = tmp_path / "projection-visuals.json"
    app = create_app(
        Settings(
            projection_dist=tmp_path / "dist",
            projection_visuals_file=settings_path,
        )
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        invalid_width = await client.put(
            "/api/v1/settings/projection-visuals",
            json={
                "approachRingWidth": 100,
                "showPerformanceInfo": False,
                "approachRingOpacity": 0.22,
                "lowPadScale": 1,
                "midPadScale": 1,
                "highPadScale": 1,
                "centerPadScale": 1,
            },
        )
        invalid_opacity = await client.put(
            "/api/v1/settings/projection-visuals",
            json={
                "approachRingWidth": 14,
                "showPerformanceInfo": False,
                "approachRingOpacity": 0,
                "lowPadScale": 1,
                "midPadScale": 1,
                "highPadScale": 1,
                "centerPadScale": 1,
            },
        )

    assert invalid_width.status_code == 422
    assert invalid_opacity.status_code == 422
    assert not settings_path.exists()
