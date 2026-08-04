from drumnext.domain.content import Score, ScoreNote


def select_note_window(
    score: Score, position_ms: float, lookahead_ms: int = 4_000
) -> list[ScoreNote]:
    window_end_ms = min(score.duration_ms, position_ms + lookahead_ms)
    return [
        note
        for note in score.notes
        if position_ms <= note.time_ms <= window_end_ms
    ]

