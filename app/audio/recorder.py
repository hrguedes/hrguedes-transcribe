from __future__ import annotations

import threading
import wave
from pathlib import Path

import numpy as np
from PySide6.QtCore import QThread, Signal

from app.audio.source import AudioSource
from app.config import SAMPLE_RATE

POLL_INTERVAL_S = 0.05


def rms_level(block: np.ndarray) -> float:
    """Nível de 0 a 1 em escala logarítmica (-60 dBFS = 0)."""
    if block.size == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(np.square(block))))
    db = 20 * np.log10(max(rms, 1e-6))
    return float(np.clip((db + 60) / 60, 0.0, 1.0))


class RecorderThread(QThread):
    """Lê a fonte de áudio e grava no WAV em blocos.

    O `wave` reescreve o cabeçalho a cada `writeframes`, então o arquivo em disco
    é um WAV válido mesmo se o app cair no meio da gravação.
    """

    level_changed = Signal(float)
    failed = Signal(str)

    def __init__(self, source: AudioSource, wav_path: Path) -> None:
        super().__init__()
        self._source = source
        self._wav_path = wav_path
        self._stop_event = threading.Event()
        self._paused = threading.Event()
        self._frames = 0

    @property
    def frames_written(self) -> int:
        return self._frames

    @property
    def seconds_written(self) -> float:
        return self._frames / SAMPLE_RATE

    def pause(self) -> None:
        self._paused.set()

    def resume(self) -> None:
        self._paused.clear()

    def request_stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        try:
            with wave.open(str(self._wav_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(SAMPLE_RATE)
                while not self._stop_event.wait(POLL_INTERVAL_S):
                    error = self._source.error
                    if error:
                        self.failed.emit(error)
                        break
                    self._write(wf, self._source.read())
                self._source.stop()
                self._write(wf, self._source.drain())
        except OSError as exc:
            self.failed.emit(f"Falha ao gravar em disco: {exc.strerror or exc}")
        finally:
            self._source.stop()
            self.level_changed.emit(0.0)

    def _write(self, wf: wave.Wave_write, block: np.ndarray) -> None:
        # Pausado: o stream continua aberto, só descartamos os frames.
        if block.size == 0 or self._paused.is_set():
            if self._paused.is_set():
                self.level_changed.emit(0.0)
            return
        pcm = (np.clip(block, -1.0, 1.0) * 32767).astype("<i2")
        wf.writeframes(pcm.tobytes())
        self._frames += len(pcm)
        self.level_changed.emit(rms_level(block))
