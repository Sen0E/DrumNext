from __future__ import annotations

import json
from enum import StrEnum
from typing import Any

from mcp.types import CallToolResult, TextContent
from pydantic import BaseModel, ConfigDict


class ErrorCode(StrEnum):
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    SCORE_NOT_FOUND = "SCORE_NOT_FOUND"
    BACKEND_UNAVAILABLE = "BACKEND_UNAVAILABLE"
    BACKEND_REJECTED = "BACKEND_REJECTED"
    BACKEND_FAILURE = "BACKEND_FAILURE"
    PROTOCOL_ERROR = "PROTOCOL_ERROR"


class ErrorPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: ErrorCode
    message: str
    retryable: bool
    details: dict[str, Any]


class McpToolError(Exception):
    def __init__(self, payload: ErrorPayload) -> None:
        self.payload = payload
        super().__init__(self.as_json())

    @classmethod
    def create(
        cls,
        code: ErrorCode,
        message: str,
        *,
        retryable: bool,
        details: dict[str, Any] | None = None,
    ) -> McpToolError:
        return cls(
            ErrorPayload(
                code=code,
                message=message,
                retryable=retryable,
                details=details or {},
            )
        )

    def with_details(self, **details: Any) -> McpToolError:
        merged = {**self.payload.details, **details}
        return McpToolError(self.payload.model_copy(update={"details": merged}))

    def as_json(self) -> str:
        return json.dumps(
            self.payload.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":")
        )

    def as_call_result(self) -> CallToolResult:
        return CallToolResult(
            isError=True,
            content=[TextContent(type="text", text=self.as_json())],
        )
