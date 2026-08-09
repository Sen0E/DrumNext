from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence

from mcp.server.fastmcp import FastMCP
from mcp.types import (
    GetPromptRequest,
    ListPromptsRequest,
    ListResourcesRequest,
    ListResourceTemplatesRequest,
    ReadResourceRequest,
)

from drumnext_mcp.api_client import DrumNextApiClient
from drumnext_mcp.config import DrumNextConfig, LimitsConfig
from drumnext_mcp.tools import DrumNextTools, register_tools


def create_server(
    client: DrumNextApiClient,
    max_scores_returned: int,
) -> FastMCP:
    server = FastMCP(name="DrumNext", log_level="ERROR")
    register_tools(server, DrumNextTools(client, max_scores_returned))
    _remove_non_tool_capabilities(server)
    return server


def _remove_non_tool_capabilities(server: FastMCP) -> None:
    request_handlers = server._mcp_server.request_handlers
    for request_type in (
        ListResourcesRequest,
        ReadResourceRequest,
        ListResourceTemplatesRequest,
        ListPromptsRequest,
        GetPromptRequest,
    ):
        request_handlers.pop(request_type, None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m drumnext_mcp.server")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--request-timeout-seconds", required=True, type=float)
    parser.add_argument("--max-scores-returned", required=True, type=int)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    drumnext = DrumNextConfig.model_validate(
        {
            "baseUrl": args.base_url,
            "requestTimeoutSeconds": args.request_timeout_seconds,
        }
    )
    limits = LimitsConfig.model_validate(
        {"maxMessageBytes": 1024, "maxScoresReturned": args.max_scores_returned}
    )
    client = DrumNextApiClient(
        drumnext.base_url,
        drumnext.request_timeout_seconds,
    )
    server = create_server(client, limits.max_scores_returned)
    try:
        server.run(transport="stdio")
    finally:
        asyncio.run(client.aclose())
    return 0


def run() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    run()
