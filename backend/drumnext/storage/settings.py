import json
from pathlib import Path

from drumnext.domain.content import EndingAnimationSettings


class EndingAnimationSettingsStore:
    def __init__(self, path: Path) -> None:
        self._path = path.resolve()

    def get(self) -> EndingAnimationSettings:
        if not self._path.is_file():
            return EndingAnimationSettings()
        return EndingAnimationSettings.model_validate(
            json.loads(self._path.read_text(encoding="utf-8"))
        )

    def update(self, settings: EndingAnimationSettings) -> EndingAnimationSettings:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".tmp")
        temporary.write_text(settings.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(self._path)
        return settings
