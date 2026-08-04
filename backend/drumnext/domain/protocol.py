from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

PROTOCOL_VERSION = 1


class PlaybackSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["stopped", "playing", "paused"]
    score_id: str = Field(alias="scoreId")
    duration_ms: int = Field(alias="durationMs", gt=0)
    position_ms: float = Field(alias="positionMs", ge=0)
    anchor_position_ms: float = Field(alias="anchorPositionMs", ge=0)
    anchor_clock_ms: float = Field(alias="anchorClockMs", ge=0)
    speed: float = Field(gt=0)


class EventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol_version: Literal[1] = Field(default=PROTOCOL_VERSION, alias="protocolVersion")
    type: str
    sequence: int = Field(ge=1)
    server_time_ms: float = Field(alias="serverTimeMs", ge=0)
    payload: dict[str, Any]


class ClockPing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["clock.ping"]
    client_time_ms: float = Field(alias="clientTimeMs", ge=0)

