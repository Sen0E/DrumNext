from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ResponseModel(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True, serialize_by_alias=True)


class PlaybackSnapshot(ResponseModel):
    status: Literal["stopped", "playing", "paused"]
    score_id: str = Field(alias="scoreId", min_length=1)
    duration_ms: int = Field(alias="durationMs", gt=0)
    position_ms: float = Field(alias="positionMs", ge=0)
    anchor_position_ms: float = Field(alias="anchorPositionMs", ge=0)
    anchor_clock_ms: float = Field(alias="anchorClockMs", ge=0)
    speed: float = Field(gt=0)


class ScoreSummary(ResponseModel):
    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=128)
    duration_ms: int = Field(alias="durationMs", gt=0)
    note_count: int = Field(alias="noteCount", ge=0)


class PlaybackResult(ResponseModel):
    message: str
    playback: PlaybackSnapshot


class ScoreListResult(ResponseModel):
    scores: list[ScoreSummary]
