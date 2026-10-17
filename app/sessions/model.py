from __future__ import annotations

import json
import os
import wave
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from app.config import SAMPLE_RATE


class SessionStatus(StrEnum):
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"
    STOPPED = "stopped"
    TRANSCRIBING = "transcribing"
    DONE = "done"
    ERROR = "error"


ALLOWED_TRANSITIONS: dict[SessionStatus, set[SessionStatus]] = {
    SessionStatus.IDLE: {SessionStatus.RECORDING},
    SessionStatus.RECORDING: {SessionStatus.PAUSED, SessionStatus.STOPPED, SessionStatus.ERROR},
    SessionStatus.PAUSED: {SessionStatus.RECORDING, SessionStatus.STOPPED, SessionStatus.ERROR},
    # TRANSCRIBING -> STOPPED é o cancelamento: o áudio fica e pode ser transcrito depois.
    SessionStatus.STOPPED: {SessionStatus.TRANSCRIBING, SessionStatus.ERROR},
    SessionStatus.TRANSCRIBING: {SessionStatus.DONE, SessionStatus.ERROR, SessionStatus.STOPPED},
    SessionStatus.DONE: {SessionStatus.TRANSCRIBING},
    SessionStatus.ERROR: {SessionStatus.TRANSCRIBING},
}

STATUS_LABELS = {
    SessionStatus.IDLE: "Nova",
    SessionStatus.RECORDING: "Gravando",
    SessionStatus.PAUSED: "Pausada",
    SessionStatus.STOPPED: "Aguardando transcrição",
    SessionStatus.TRANSCRIBING: "Transcrevendo",
    SessionStatus.DONE: "Concluída",
    SessionStatus.ERROR: "Erro",
}


class InvalidTransition(RuntimeError):
    pass


@dataclass
class Segment:
    start: float
    end: float
    text: str


def write_json_atomic(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


@dataclass
class Session:
    id: str
    path: Path
    title: str
    created_at: str
    duration: float = 0.0
    status: SessionStatus = SessionStatus.IDLE
    error: str | None = None
    model: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def audio_path(self) -> Path:
        return self.path / "audio.wav"

    @property
    def transcript_path(self) -> Path:
        return self.path / "transcript.json"

    @property
    def meta_path(self) -> Path:
        return self.path / "meta.json"

    @property
    def created_datetime(self) -> datetime:
        return datetime.fromisoformat(self.created_at)

    @property
    def has_transcript(self) -> bool:
        return self.transcript_path.exists()

    def transition(self, new: SessionStatus) -> None:
        if new not in ALLOWED_TRANSITIONS[self.status]:
            raise InvalidTransition(f"{self.status} -> {new}")
        self.status = new
        if new is not SessionStatus.ERROR:
            self.error = None
        self.save_meta()

    def fail(self, message: str) -> None:
        self.status = SessionStatus.ERROR
        self.error = message
        self.save_meta()

    def save_meta(self) -> None:
        data = asdict(self)
        data.pop("path")
        data["status"] = str(self.status)
        write_json_atomic(self.meta_path, data)

    def save_transcript(self, segments: list[Segment], language: str | None, model: str | None) -> None:
        write_json_atomic(
            self.transcript_path,
            {
                "language": language,
                "model": model,
                "segments": [asdict(s) for s in segments],
            },
        )
        self.model = model

    def load_transcript(self) -> list[Segment]:
        if not self.transcript_path.exists():
            return []
        with open(self.transcript_path, encoding="utf-8") as fh:
            data = json.load(fh)
        return [Segment(**s) for s in data.get("segments", [])]

    def audio_duration(self) -> float:
        if not self.audio_path.exists():
            return 0.0
        try:
            with wave.open(str(self.audio_path), "rb") as wf:
                return wf.getnframes() / wf.getframerate()
        except (wave.Error, EOFError):
            # Cabeçalho incompleto (queda do app): estima pelo tamanho do arquivo.
            size = self.audio_path.stat().st_size
            return max(0, size - 44) / 2 / SAMPLE_RATE

    @classmethod
    def load(cls, path: Path) -> Session:
        with open(path / "meta.json", encoding="utf-8") as fh:
            data = json.load(fh)
        data["status"] = SessionStatus(data.get("status", SessionStatus.IDLE))
        return cls(path=path, **data)
