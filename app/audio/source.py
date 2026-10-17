from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np

# Dispositivos de entrada que carregam o áudio do sistema (o que sai nos alto-falantes).
LOOPBACK_NAMES = ("blackhole", "stereo mix", "mixagem estéreo", "mixagem estereo", "cable output")


class AudioSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class AudioDevice:
    index: int
    name: str
    channels: int
    samplerate: float
    hostapi: str = ""

    @property
    def is_loopback(self) -> bool:
        name = self.name.lower()
        return any(n in name for n in LOOPBACK_NAMES)

    @property
    def is_wasapi(self) -> bool:
        return "wasapi" in self.hostapi.lower()


class AudioSource(ABC):
    """Fonte de áudio já mixada: entrega float32 mono a `SAMPLE_RATE`.

    `read()` não bloqueia e devolve tudo o que chegou desde a última chamada.
    O stream fica aberto entre `start()` e `stop()`; pausar é responsabilidade
    de quem consome (descartando o que for lido).
    """

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def read(self) -> np.ndarray: ...

    @abstractmethod
    def stop(self) -> None: ...

    def drain(self) -> np.ndarray:
        """Último bloco depois de `stop()`."""
        return self.read()

    @property
    @abstractmethod
    def error(self) -> str | None:
        """Mensagem de erro se algum dispositivo caiu durante a captura."""
