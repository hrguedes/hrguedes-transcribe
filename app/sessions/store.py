from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

from app.sessions.model import Session, SessionStatus

log = logging.getLogger(__name__)


class SessionStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def create(self, title: str | None = None) -> Session:
        now = datetime.now().astimezone()
        session_id = f"{now:%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
        path = self.root / session_id
        path.mkdir(parents=True)
        session = Session(
            id=session_id,
            path=path,
            title=title or f"Reunião {now:%d/%m/%Y %H:%M}",
            created_at=now.isoformat(timespec="seconds"),
        )
        session.save_meta()
        return session

    def list(self) -> list[Session]:
        sessions: list[Session] = []
        for path in self.root.iterdir():
            if not (path / "meta.json").is_file():
                continue
            try:
                sessions.append(Session.load(path))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                log.exception("Sessão ilegível ignorada: %s", path)
        sessions.sort(key=lambda s: s.created_at, reverse=True)
        return sessions

    def recover_interrupted(self) -> list[Session]:
        """Sessões que estavam gravando/transcrevendo quando o app caiu voltam para `stopped`."""
        recovered = []
        for session in self.list():
            if session.status in (SessionStatus.RECORDING, SessionStatus.PAUSED, SessionStatus.TRANSCRIBING):
                session.duration = session.audio_duration()
                session.status = SessionStatus.STOPPED
                session.extra["recovered"] = True
                session.save_meta()
                recovered.append(session)
            elif session.status is SessionStatus.IDLE and not session.audio_path.exists():
                # Sessão criada mas nunca gravada.
                for child in session.path.iterdir():
                    child.unlink()
                session.path.rmdir()
        return recovered
