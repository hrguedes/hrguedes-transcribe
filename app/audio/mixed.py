from __future__ import annotations

import numpy as np

from app.audio.capture import StreamCapture
from app.audio.source import AudioDevice, AudioSource, AudioSourceError
from app.config import SAMPLE_RATE

# Se uma trilha atrasar mais que isso em relação à outra (dispositivo mudo ou
# travado), completamos com silêncio para não represar a gravação.
MAX_DRIFT_SAMPLES = SAMPLE_RATE // 2


class TrackMixer:
    def __init__(self) -> None:
        self._a = np.zeros(0, dtype=np.float32)
        self._b = np.zeros(0, dtype=np.float32)

    def push(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        self._a = np.concatenate([self._a, a])
        self._b = np.concatenate([self._b, b])
        if abs(len(self._a) - len(self._b)) > MAX_DRIFT_SAMPLES:
            n = max(len(self._a), len(self._b))
            self._a = np.pad(self._a, (0, n - len(self._a)))
            self._b = np.pad(self._b, (0, n - len(self._b)))
        n = min(len(self._a), len(self._b))
        mixed = np.clip(self._a[:n] + self._b[:n], -1.0, 1.0)
        self._a = self._a[n:]
        self._b = self._b[n:]
        return mixed

    def flush(self) -> np.ndarray:
        n = max(len(self._a), len(self._b))
        a = np.pad(self._a, (0, n - len(self._a)))
        b = np.pad(self._b, (0, n - len(self._b)))
        self._a = self._b = np.zeros(0, dtype=np.float32)
        return np.clip(a + b, -1.0, 1.0)


class MixedInputSource(AudioSource):
    """Microfone + um dispositivo de entrada com o áudio do sistema, mixados em mono.

    No macOS o áudio do sistema vem do BlackHole; no Windows, da "Mixagem estéreo".
    """

    def __init__(self, mic: AudioDevice | None, system: AudioDevice | None) -> None:
        if mic is None and system is None:
            raise AudioSourceError("Nenhum dispositivo de entrada selecionado.")
        self._mic = StreamCapture(mic, "Microfone") if mic else None
        self._system = StreamCapture(system, "Áudio do sistema") if system else None
        self._mixer = TrackMixer()

    @property
    def _captures(self) -> list[StreamCapture]:
        return [c for c in (self._mic, self._system) if c is not None]

    def start(self) -> None:
        started = []
        try:
            for capture in self._captures:
                capture.start()
                started.append(capture)
        except AudioSourceError:
            for capture in started:
                capture.stop()
            raise

    def read(self) -> np.ndarray:
        if self._mic and self._system:
            return self._mixer.push(self._mic.read(), self._system.read())
        return self._captures[0].read()

    def stop(self) -> None:
        for capture in self._captures:
            capture.stop()

    def drain(self) -> np.ndarray:
        """Último bloco depois de `stop()`, incluindo o que sobrou no mixer."""
        tail = self.read()
        if self._mic and self._system:
            tail = np.concatenate([tail, self._mixer.flush()])
        return tail

    @property
    def error(self) -> str | None:
        return next((c.error for c in self._captures if c.error), None)
