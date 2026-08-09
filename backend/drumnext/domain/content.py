import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

NOTE_KEY_PATTERN = re.compile(r"^(low|mid|high)_[1-7](_center)?$")


class ScoreNote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    time_ms: int = Field(alias="timeMs", ge=0)
    note_key: str = Field(alias="noteKey")
    velocity: float = Field(default=1, ge=0, le=1)

    @field_validator("note_key")
    @classmethod
    def validate_note_key(cls, value: str) -> str:
        if NOTE_KEY_PATTERN.fullmatch(value) is None:
            raise ValueError("invalid noteKey")
        return value


class Score(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(alias="schemaVersion")
    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=128)
    duration_ms: int = Field(alias="durationMs", gt=0)
    notes: list[ScoreNote] = Field(max_length=20_000)

    @model_validator(mode="after")
    def validate_notes(self) -> "Score":
        if "/" in self.id or "\\" in self.id or self.id in {".", ".."}:
            raise ValueError("invalid score id")
        if self.schema_version != 1:
            raise ValueError("unsupported score schemaVersion")
        if len({note.id for note in self.notes}) != len(self.notes):
            raise ValueError("note ids must be unique")
        if self.notes != sorted(self.notes, key=lambda note: note.time_ms):
            raise ValueError("notes must be sorted by timeMs")
        if any(note.time_ms > self.duration_ms for note in self.notes):
            raise ValueError("note timeMs exceeds durationMs")
        return self


class ScoreSummary(BaseModel):
    id: str
    title: str
    duration_ms: int = Field(alias="durationMs")
    note_count: int = Field(alias="noteCount")


class LayoutPad(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note_key: str = Field(alias="noteKey")
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    radius: float = Field(gt=0, le=0.25)
    color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$")
    label: str = Field(min_length=1, max_length=16)
    octave_label: str = Field(alias="octaveLabel", min_length=1, max_length=8)
    audio_asset: str = Field(alias="audioAsset", min_length=1, max_length=128)

    _validate_note_key = field_validator("note_key")(ScoreNote.validate_note_key.__func__)


class Layout(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(alias="schemaVersion")
    revision: int = Field(ge=1)
    pads: list[LayoutPad] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_layout(self) -> "Layout":
        if self.schema_version != 1:
            raise ValueError("unsupported layout schemaVersion")
        keys = [pad.note_key for pad in self.pads]
        if len(set(keys)) != len(keys):
            raise ValueError("layout noteKeys must be unique")
        return self


class EndingAnimationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style: Literal["calm", "spectacular"] = "calm"
