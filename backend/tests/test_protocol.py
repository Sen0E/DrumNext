import json
from pathlib import Path

from drumnext.domain.protocol import EventEnvelope, PlaybackSnapshot

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_python_parses_shared_snapshot_fixture() -> None:
    fixture_path = PROJECT_ROOT / "shared" / "fixtures" / "playback-snapshot.json"
    fixture = EventEnvelope.model_validate(json.loads(fixture_path.read_text(encoding="utf-8")))
    snapshot = PlaybackSnapshot.model_validate(fixture.payload)

    assert fixture.protocol_version == 1
    assert snapshot.status == "playing"
    assert snapshot.position_ms == 2_500
