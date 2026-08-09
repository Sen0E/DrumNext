from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DRUMNEXT_", extra="ignore")

    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    projection_dist: Path = PROJECT_ROOT / "dist"
    score_directory: Path = PROJECT_ROOT / "resources" / "scores"
    layout_file: Path = PROJECT_ROOT / "config" / "default-layout.json"
    user_layout_file: Path = PROJECT_ROOT / "config" / "user-layout.json"
    ending_animation_file: Path = PROJECT_ROOT / "config" / "ending-animation.json"
    projection_visuals_file: Path = PROJECT_ROOT / "config" / "projection-visuals.json"
    default_score_id: str = "大鱼"


settings = Settings()
