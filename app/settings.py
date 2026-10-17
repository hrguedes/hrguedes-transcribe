from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.config import WHISPER_MODEL, app_data_dir
from app.sessions.model import write_json_atomic

log = logging.getLogger(__name__)


@dataclass
class Settings:
    model: str = WHISPER_MODEL
    vocabulary: list[str] = field(default_factory=list)

    @staticmethod
    def parse_vocabulary(text: str) -> list[str]:
        """Um termo por linha ou separados por vírgula/ponto e vírgula."""
        seen: dict[str, None] = {}
        for term in re.split(r"[\n,;]+", text):
            term = term.strip()
            if term and term.lower() not in (k.lower() for k in seen):
                seen[term] = None
        return list(seen)


def settings_path() -> Path:
    return app_data_dir() / "settings.json"


def load_settings(path: Path | None = None) -> Settings:
    path = path or settings_path()
    if not path.exists():
        return Settings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        defaults = Settings()
        return Settings(
            model=str(data.get("model") or defaults.model),
            vocabulary=[str(v) for v in data.get("vocabulary", [])],
        )
    except (OSError, ValueError, TypeError):
        log.exception("settings.json ilegível; usando padrões")
        return Settings()


def save_settings(settings: Settings, path: Path | None = None) -> None:
    write_json_atomic(path or settings_path(), asdict(settings))
