import json
from pathlib import Path

from drumnext.domain.content import Layout, Score, ScoreSummary


class ContentNotFoundError(LookupError):
    pass


class ScoreStore:
    def __init__(self, directory: Path) -> None:
        self._directory = directory.resolve()

    def list(self) -> list[ScoreSummary]:
        summaries = []
        for path in sorted(self._directory.glob("*.json")):
            score = self._read(path)
            summaries.append(
                ScoreSummary(
                    id=score.id,
                    title=score.title,
                    durationMs=score.duration_ms,
                    noteCount=len(score.notes),
                )
            )
        return summaries

    def get(self, score_id: str) -> Score:
        if not score_id or "/" in score_id or "\\" in score_id or score_id in {".", ".."}:
            raise ContentNotFoundError(score_id)

        for path in self._directory.glob("*.json"):
            score = self._read(path)
            if score.id == score_id:
                return score
        raise ContentNotFoundError(score_id)

    @staticmethod
    def _read(path: Path) -> Score:
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, list):
            return _legacy_score(path.stem, value)
        return Score.model_validate(value)


def _legacy_score(score_id: str, rows: list[object]) -> Score:
    notes = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, list) or len(row) != 2:
            raise ValueError("legacy score rows must contain [timeMs, noteKey]")
        time_ms, note_key = row
        notes.append(
            {
                "id": f"legacy-{index:06d}",
                "timeMs": time_ms,
                "noteKey": note_key,
                "velocity": 1,
            }
        )
    times = (note["timeMs"] for note in notes if isinstance(note["timeMs"], int))
    duration_ms = max(times, default=0) + 2_000
    return Score.model_validate(
        {
            "schemaVersion": 1,
            "id": score_id,
            "title": score_id,
            "durationMs": duration_ms,
            "notes": notes,
        }
    )


class LayoutStore:
    def __init__(self, path: Path) -> None:
        self._path = path.resolve()

    def get(self) -> Layout:
        return Layout.model_validate(json.loads(self._path.read_text(encoding="utf-8")))

    def update(self, layout: Layout) -> Layout:
        current = self.get()
        updated = layout.model_copy(update={"revision": current.revision + 1})
        temporary = self._path.with_suffix(".tmp")
        temporary.write_text(
            updated.model_dump_json(by_alias=True, indent=2), encoding="utf-8"
        )
        temporary.replace(self._path)
        return updated
