from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from app.transcription.transcriber import Transcriber, TranscriptionCancelled


class TranscriptionWorker(QObject):
    """Roda em uma QThread; só conversa com a UI por signals."""

    progress = Signal(float)
    status = Signal(str)
    finished = Signal(object)  # TranscriptionResult
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, transcriber: Transcriber, audio_path: Path) -> None:
        super().__init__()
        self._transcriber = transcriber
        self._audio_path = audio_path
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    @Slot()
    def run(self) -> None:
        try:
            result = self._transcriber.transcribe(
                self._audio_path,
                on_progress=self.progress.emit,
                on_status=self.status.emit,
                should_cancel=self._cancel.is_set,
            )
        except TranscriptionCancelled:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        else:
            self.finished.emit(result)
