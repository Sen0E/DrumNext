import json

from drumnext.config import PROJECT_ROOT
from drumnext.domain.content import Score
from drumnext.playback.scheduling import select_note_window


def demo_score() -> Score:
    path = PROJECT_ROOT / "resources/scores/demo-score.json"
    return Score.model_validate(json.loads(path.read_text(encoding="utf-8")))


def test_selects_inclusive_note_window_without_waiting() -> None:
    notes = select_note_window(demo_score(), 1_900, 1_800)
    assert [note.id for note in notes] == ["demo-02", "demo-03", "demo-04"]


def test_clamps_window_to_score_duration() -> None:
    notes = select_note_window(demo_score(), 13_000, 10_000)
    assert [note.id for note in notes] == ["demo-15"]

