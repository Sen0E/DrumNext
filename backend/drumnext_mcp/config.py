from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    ValidationError,
    WebsocketUrl,
    field_validator,
    model_validator,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "xiaozhi-mcp.json"


class ConfigError(ValueError):
    """A safe, user-facing configuration error."""


class StrictConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EndpointConfig(StrictConfigModel):
    url: WebsocketUrl = Field(repr=False)
    connect_timeout_seconds: int = Field(alias="connectTimeoutSeconds", ge=1, le=120)
    ping_interval_seconds: int = Field(alias="pingIntervalSeconds", ge=5, le=300)
    ping_timeout_seconds: int = Field(alias="pingTimeoutSeconds", ge=5, le=300)


class DrumNextConfig(StrictConfigModel):
    base_url: HttpUrl = Field(alias="baseUrl")
    request_timeout_seconds: float = Field(
        alias="requestTimeoutSeconds", ge=0.1, le=120
    )

    @field_validator("base_url")
    @classmethod
    def validate_base_url_is_root(cls, value: HttpUrl) -> HttpUrl:
        if value.path not in {None, "", "/"} or value.query or value.fragment:
            raise ValueError("baseUrl must be an HTTP(S) root URL without path, query, or fragment")
        return value


class ReconnectConfig(StrictConfigModel):
    initial_delay_seconds: float = Field(alias="initialDelaySeconds", ge=0.1, le=60)
    max_delay_seconds: float = Field(alias="maxDelaySeconds", ge=0.1)
    multiplier: float = Field(ge=1, le=10)
    jitter_ratio: float = Field(alias="jitterRatio", ge=0, le=1)
    stable_reset_seconds: int = Field(alias="stableResetSeconds", ge=1, le=3600)

    @model_validator(mode="after")
    def validate_delay_order(self) -> ReconnectConfig:
        if self.max_delay_seconds < self.initial_delay_seconds:
            raise ValueError("maxDelaySeconds must be greater than or equal to initialDelaySeconds")
        return self


class LimitsConfig(StrictConfigModel):
    max_message_bytes: int = Field(alias="maxMessageBytes", ge=1024, le=16_777_216)
    max_scores_returned: int = Field(alias="maxScoresReturned", ge=1, le=1000)


class ProcessConfig(StrictConfigModel):
    shutdown_grace_seconds: float = Field(alias="shutdownGraceSeconds", ge=0.1, le=60)
    terminate_grace_seconds: float = Field(alias="terminateGraceSeconds", ge=0.1, le=60)


class LoggingConfig(StrictConfigModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]
    format: Literal["text", "json"]


class McpConfig(StrictConfigModel):
    schema_version: Literal[1] = Field(alias="schemaVersion")
    endpoint: EndpointConfig
    drumnext: DrumNextConfig
    reconnect: ReconnectConfig
    limits: LimitsConfig
    process: ProcessConfig
    logging: LoggingConfig

    def redacted_log_view(self) -> dict[str, Any]:
        """Return a JSON-compatible configuration view safe for application logs."""
        view = self.model_dump(mode="json", by_alias=True)
        view["endpoint"]["url"] = redact_endpoint(self.endpoint.url)
        return view


def redact_endpoint(endpoint: WebsocketUrl) -> str:
    """Keep only an endpoint's scheme and authority, omitting credentials and route data."""
    parsed = urlsplit(str(endpoint))
    host = parsed.hostname or "unknown-host"
    if ":" in host:
        host = f"[{host}]"
    authority = f"{host}:{parsed.port}" if parsed.port is not None else host
    return f"{parsed.scheme}://{authority}/***"


def load_config(path: str | Path | None = None) -> McpConfig:
    """Load and validate MCP configuration without exposing file contents in errors."""
    config_path = Path(path).expanduser() if path is not None else DEFAULT_CONFIG_PATH
    try:
        raw = config_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigError(f"configuration file does not exist: {config_path}") from None
    except OSError:
        raise ConfigError(f"cannot read configuration file: {config_path}") from None
    except UnicodeDecodeError:
        raise ConfigError(f"configuration file is not valid UTF-8: {config_path}") from None

    try:
        document = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ConfigError(
            f"configuration file is not valid JSON at line {error.lineno}, column {error.colno}"
        ) from None

    try:
        return McpConfig.model_validate(document)
    except ValidationError as error:
        issues = [_format_validation_issue(issue) for issue in error.errors(include_input=False)]
        raise ConfigError("invalid configuration: " + "; ".join(issues)) from None


def _format_validation_issue(issue: dict[str, Any]) -> str:
    location = ".".join(str(part) for part in issue.get("loc", ())) or "configuration"
    return f"{location}: {issue.get('msg', 'invalid value')}"
