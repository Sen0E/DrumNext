from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

import drumnext_mcp.config as config_module
from drumnext_mcp.config import ConfigError, load_config

PROJECT_ROOT = Path(__file__).resolve().parents[3]
EXAMPLE_CONFIG = PROJECT_ROOT / "config" / "xiaozhi-mcp.example.json"


@pytest.fixture
def valid_document() -> dict[str, object]:
    return json.loads(EXAMPLE_CONFIG.read_text(encoding="utf-8"))


def write_config(path: Path, document: object) -> Path:
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_complete_example_config_loads() -> None:
    config = load_config(EXAMPLE_CONFIG)

    assert config.schema_version == 1
    assert str(config.endpoint.url).startswith("wss://replace-with-your-xiaozhi-mcp-endpoint")
    assert str(config.drumnext.base_url) == "http://127.0.0.1:8000/"


@pytest.mark.parametrize(
    ("mutation", "expected_location"),
    [
        (lambda document: document.pop("endpoint"), "endpoint"),
        (lambda document: document["endpoint"].update(url="ftp://invalid"), "endpoint.url"),
        (lambda document: document.update(schemaVersion=2), "schemaVersion"),
        (lambda document: document.update(unknown=True), "unknown"),
        (lambda document: document["limits"].update(unknown=True), "limits.unknown"),
        (
            lambda document: document["drumnext"].update(
                baseUrl="http://127.0.0.1:8000/api/v1"
            ),
            "drumnext.baseUrl",
        ),
    ],
)
def test_invalid_config_is_rejected(
    tmp_path: Path,
    valid_document: dict[str, object],
    mutation: object,
    expected_location: str,
) -> None:
    document = deepcopy(valid_document)
    mutation(document)  # type: ignore[operator]

    with pytest.raises(ConfigError, match=expected_location):
        load_config(write_config(tmp_path / "config.json", document))


@pytest.mark.parametrize(
    ("section", "field", "accepted"),
    [
        ("endpoint", "connectTimeoutSeconds", [1, 120]),
        ("endpoint", "pingIntervalSeconds", [5, 300]),
        ("drumnext", "requestTimeoutSeconds", [0.1, 120]),
        ("reconnect", "initialDelaySeconds", [0.1, 60]),
        ("reconnect", "multiplier", [1, 10]),
        ("reconnect", "jitterRatio", [0, 1]),
        ("limits", "maxMessageBytes", [1024, 16_777_216]),
        ("limits", "maxScoresReturned", [1, 1000]),
        ("process", "shutdownGraceSeconds", [0.1, 60]),
    ],
)
def test_numeric_boundaries_are_accepted(
    tmp_path: Path,
    valid_document: dict[str, object],
    section: str,
    field: str,
    accepted: list[int | float],
) -> None:
    for value in accepted:
        document = deepcopy(valid_document)
        document[section][field] = value  # type: ignore[index]
        load_config(write_config(tmp_path / f"{section}-{field}-{value}.json", document))


@pytest.mark.parametrize(
    ("section", "field", "rejected"),
    [
        ("endpoint", "connectTimeoutSeconds", [0, 121]),
        ("endpoint", "pingIntervalSeconds", [4, 301]),
        ("endpoint", "pingTimeoutSeconds", [4, 301]),
        ("drumnext", "requestTimeoutSeconds", [0.09, 121]),
        ("reconnect", "initialDelaySeconds", [0.09, 61]),
        ("reconnect", "multiplier", [0.9, 10.1]),
        ("reconnect", "jitterRatio", [-0.1, 1.1]),
        ("reconnect", "stableResetSeconds", [0, 3601]),
        ("limits", "maxMessageBytes", [1023, 16_777_217]),
        ("limits", "maxScoresReturned", [0, 1001]),
        ("process", "shutdownGraceSeconds", [0.09, 61]),
        ("process", "terminateGraceSeconds", [0.09, 61]),
    ],
)
def test_numeric_values_outside_boundaries_are_rejected(
    tmp_path: Path,
    valid_document: dict[str, object],
    section: str,
    field: str,
    rejected: list[int | float],
) -> None:
    for value in rejected:
        document = deepcopy(valid_document)
        document[section][field] = value  # type: ignore[index]
        with pytest.raises(ConfigError, match=field):
            load_config(write_config(tmp_path / f"{section}-{field}-{value}.json", document))


def test_backoff_maximum_cannot_be_smaller_than_initial(
    tmp_path: Path, valid_document: dict[str, object]
) -> None:
    valid_document["reconnect"]["initialDelaySeconds"] = 10  # type: ignore[index]
    valid_document["reconnect"]["maxDelaySeconds"] = 9  # type: ignore[index]

    with pytest.raises(ConfigError, match="maxDelaySeconds"):
        load_config(write_config(tmp_path / "config.json", valid_document))


def test_types_are_strict(tmp_path: Path, valid_document: dict[str, object]) -> None:
    valid_document["limits"]["maxMessageBytes"] = "1048576"  # type: ignore[index]

    with pytest.raises(ConfigError, match="limits.maxMessageBytes"):
        load_config(write_config(tmp_path / "config.json", valid_document))


def test_redacted_log_view_hides_endpoint_secrets(
    tmp_path: Path, valid_document: dict[str, object]
) -> None:
    secret = "very-secret-token"
    endpoint = f"wss://user:password@example.test:8443/private/mcp?token={secret}"
    valid_document["endpoint"]["url"] = endpoint  # type: ignore[index]

    config = load_config(write_config(tmp_path / "config.json", valid_document))
    serialized = json.dumps(config.redacted_log_view())

    assert config.redacted_log_view()["endpoint"]["url"] == "wss://example.test:8443/***"
    assert secret not in serialized
    assert "password" not in serialized
    assert "/private/mcp" not in serialized
    assert endpoint not in repr(config)


def test_validation_error_does_not_echo_endpoint(
    tmp_path: Path, valid_document: dict[str, object]
) -> None:
    secret = "do-not-echo-this-token"
    valid_document["endpoint"]["url"] = f"wss://example.test/mcp?token={secret}"  # type: ignore[index]
    valid_document["limits"]["maxMessageBytes"] = 1  # type: ignore[index]

    with pytest.raises(ConfigError) as captured:
        load_config(write_config(tmp_path / "config.json", valid_document))

    assert secret not in str(captured.value)


def test_default_path_does_not_depend_on_working_directory(
    tmp_path: Path, valid_document: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    configured_path = write_config(tmp_path / "xiaozhi-mcp.json", valid_document)
    other_directory = tmp_path / "elsewhere"
    other_directory.mkdir()
    monkeypatch.setattr(config_module, "DEFAULT_CONFIG_PATH", configured_path)
    monkeypatch.chdir(other_directory)

    assert load_config().schema_version == 1


def test_missing_and_invalid_files_have_clear_errors(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="does not exist"):
        load_config(tmp_path / "missing.json")

    invalid = tmp_path / "invalid.json"
    invalid.write_text("{not JSON and not a secret value}", encoding="utf-8")
    with pytest.raises(ConfigError, match="not valid JSON") as captured:
        load_config(invalid)
    assert "not a secret value" not in str(captured.value)
