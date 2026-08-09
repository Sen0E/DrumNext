import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from drumnext.config import PROJECT_ROOT, Settings
from drumnext.main import create_app


def content_settings(tmp_path: Path) -> Settings:
    scores = tmp_path / "scores"
    scores.mkdir()
    (scores / "demo-score.json").write_text(
        (PROJECT_ROOT / "resources/scores/demo-score.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    layout = tmp_path / "layout.json"
    layout.write_text(
        (PROJECT_ROOT / "config/default-layout.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return Settings(
        projection_dist=tmp_path / "dist",
        score_directory=scores,
        layout_file=layout,
        user_layout_file=tmp_path / "user-layout.json",
    )


@pytest.mark.anyio
async def test_lists_gets_and_selects_scores(tmp_path: Path) -> None:
    app = create_app(content_settings(tmp_path))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listing = await client.get("/api/v1/scores")
        score = await client.get("/api/v1/scores/demo-score")
        selected = await client.post(
            "/api/v1/playback/score", json={"scoreId": "demo-score"}
        )

    assert listing.json()[0] == {
        "id": "demo-score",
        "title": "DrumNext 演示乐谱",
        "durationMs": 16_000,
        "noteCount": 15,
    }
    assert len(score.json()["notes"]) == 15
    assert selected.json()["scoreId"] == "demo-score"


@pytest.mark.anyio
async def test_score_not_found_has_machine_readable_error(tmp_path: Path) -> None:
    app = create_app(content_settings(tmp_path))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/scores/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SCORE_NOT_FOUND"


@pytest.mark.anyio
async def test_layout_update_is_validated_and_increments_revision(tmp_path: Path) -> None:
    settings = content_settings(tmp_path)
    default_contents = settings.layout_file.read_text(encoding="utf-8")
    app = create_app(settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        current = (await client.get("/api/v1/layout")).json()
        current["pads"][0]["x"] = 0.3
        updated = await client.put("/api/v1/layout", json=current)
        loaded = await client.get("/api/v1/layout")

    assert updated.status_code == 200
    assert updated.json()["revision"] == current["revision"] + 1
    assert updated.json()["pads"][0]["x"] == 0.3
    assert loaded.json() == updated.json()
    assert settings.layout_file.read_text(encoding="utf-8") == default_contents
    assert settings.user_layout_file.is_file()
    saved = json.loads(settings.user_layout_file.read_text(encoding="utf-8"))
    assert saved["pads"][0]["x"] == 0.3


@pytest.mark.anyio
async def test_layout_reset_deletes_user_layout_and_restores_default(tmp_path: Path) -> None:
    settings = content_settings(tmp_path)
    default = json.loads(settings.layout_file.read_text(encoding="utf-8"))
    app = create_app(settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        customized = (await client.get("/api/v1/layout")).json()
        customized["pads"][0]["x"] = 0.3
        await client.put("/api/v1/layout", json=customized)

        reset = await client.post("/api/v1/layout/reset")
        current = await client.get("/api/v1/layout")

    assert reset.status_code == 200
    assert reset.json() == default
    assert current.json() == default
    assert not settings.user_layout_file.exists()
