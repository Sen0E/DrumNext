from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from drumnext_mcp.bridge import main

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MCP_PACKAGE = PROJECT_ROOT / "backend" / "drumnext_mcp"


def test_mcp_package_does_not_import_drumnext() -> None:
    violations: list[str] = []
    for source_path in MCP_PACKAGE.glob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                violations.extend(
                    f"{source_path.name}:{alias.name}"
                    for alias in node.names
                    if alias.name == "drumnext" or alias.name.startswith("drumnext.")
                )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "drumnext" or module.startswith("drumnext."):
                    violations.append(f"{source_path.name}:{module}")

    assert violations == []


def test_existing_fastapi_entrypoint_does_not_reference_mcp() -> None:
    source = (PROJECT_ROOT / "backend" / "drumnext" / "main.py").read_text(encoding="utf-8")

    assert "drumnext_mcp" not in source


def test_cli_reports_missing_default_configuration(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["--config", str(tmp_path / "missing.json")])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "configuration error" in captured.err
    assert "does not exist" in captured.err


def test_cli_only_logs_redacted_endpoint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    document = json.loads(
        (PROJECT_ROOT / "config" / "xiaozhi-mcp.example.json").read_text(encoding="utf-8")
    )
    secret = "cli-secret-token"
    document["endpoint"]["url"] = f"wss://example.test/private?token={secret}"
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(document), encoding="utf-8")

    async def stop_immediately(_config: object) -> None:
        pass

    exit_code = main(
        ["--config", str(config_path)], bridge_runner=stop_immediately  # type: ignore[arg-type]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "wss://example.test/***" in captured.err
    assert secret not in captured.err
    assert "/private" not in captured.err
