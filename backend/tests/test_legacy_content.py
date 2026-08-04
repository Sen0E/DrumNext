from drumnext.config import PROJECT_ROOT
from drumnext.storage.content import ScoreStore


def test_imports_legacy_dayu_score_without_modifying_source() -> None:
    scores = ScoreStore(PROJECT_ROOT / "resources/scores")
    dayu = scores.get("大鱼")

    assert dayu.title == "大鱼"
    assert len(dayu.notes) == 365
    assert dayu.notes[0].time_ms == 3_692
    assert dayu.notes[0].note_key == "low_4"
    assert dayu.notes[-1].note_key == "low_6"
    assert dayu.duration_ms == 168_154


def test_migrated_layout_uses_source_pixel_coordinates() -> None:
    from drumnext.storage.content import LayoutStore

    layout = LayoutStore(PROJECT_ROOT / "config/default-layout.json").get()
    pads = {pad.note_key: pad for pad in layout.pads}

    assert pads["low_3_center"].x == 0.5
    assert pads["low_3_center"].y == 0.5
    assert pads["high_3"].x == 0.5
    assert pads["high_3"].y == 0.1481
