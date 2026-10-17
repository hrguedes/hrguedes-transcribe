from __future__ import annotations

import os
import wave
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.config import SAMPLE_RATE
from app.sessions.model import Segment
from app.transcription import models
from app.transcription.postprocess import clean_segments

ProgressCallback = Callable[[float], None]
StatusCallback = Callable[[str], None]
CancelCheck = Callable[[], bool]

BASE_PROMPT = "Transcrição de uma reunião de trabalho em português do Brasil, com pontuação e acentuação corretas."

# Silero VAD: o padrão corta o começo/fim das falas em conversas rápidas.
VAD_PARAMETERS = {
    "threshold": 0.4,
    "min_silence_duration_ms": 700,
    "speech_pad_ms": 500,
}


class TranscriptionCancelled(Exception):
    pass


class ModelNotDownloaded(RuntimeError):
    def __init__(self, model_id: str) -> None:
        info = models.get_model_info(model_id)
        super().__init__(
            f"O modelo '{info.label}' ainda não foi baixado. Baixe-o em Configurações ou escolha outro modelo."
        )
        self.model_id = model_id


@dataclass
class TranscriptionResult:
    segments: list[Segment]
    language: str | None
    duration: float


def read_wav(path: Path) -> np.ndarray:
    """WAV PCM16 mono 16 kHz -> float32, sem depender do decodificador do PyAV."""
    with wave.open(str(path), "rb") as wf:
        if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getframerate() != SAMPLE_RATE:
            raise ValueError(f"Formato de áudio inesperado em {path.name}")
        pcm = wf.readframes(wf.getnframes())
    return np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0


def build_prompts(vocabulary: list[str]) -> tuple[str, str | None]:
    """(initial_prompt, hotwords). O initial_prompt só vale para a primeira janela de
    30 s; os hotwords são reaplicados em todas, por isso o vocabulário vai neles."""
    if not vocabulary:
        return BASE_PROMPT, None
    terms = ", ".join(vocabulary)
    return f"{BASE_PROMPT} Termos citados: {terms}.", terms


class Transcriber(ABC):
    name: str
    model_id: str

    def set_vocabulary(self, vocabulary: list[str]) -> None:  # noqa: B027
        """Opcional: engines que aceitam vocabulário personalizado sobrescrevem."""

    def is_available(self) -> bool:
        """Se o modelo está pronto para uso nesta máquina, sem baixar nada."""
        return True

    @abstractmethod
    def transcribe(
        self,
        audio_path: Path,
        on_progress: ProgressCallback,
        on_status: StatusCallback,
        should_cancel: CancelCheck,
    ) -> TranscriptionResult: ...


class FasterWhisperTranscriber(Transcriber):
    def __init__(
        self,
        model_id: str,
        models_dir: Path,
        language: str = "pt",
        vocabulary: list[str] | None = None,
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> None:
        self.model_id = model_id
        self.models_dir = models_dir
        self.language = language
        self.vocabulary = list(vocabulary or [])
        self.device = device
        self.compute_type = compute_type
        self.name = f"faster-whisper-{model_id}"
        self._model = None

    @property
    def model_path(self) -> Path:
        return models.model_dir(self.models_dir, self.model_id)

    def set_vocabulary(self, vocabulary: list[str]) -> None:
        self.vocabulary = list(vocabulary)

    def is_available(self) -> bool:
        return models.is_downloaded(self.models_dir, self.model_id)

    def _load(self, on_status: StatusCallback):
        if self._model is None:
            if not self.is_available():
                raise ModelNotDownloaded(self.model_id)
            on_status(f"Carregando o modelo {models.get_model_info(self.model_id).label}…")
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                str(self.model_path),
                device=self.device,
                compute_type=self.compute_type,
                cpu_threads=min(8, os.cpu_count() or 4),
                local_files_only=True,
            )
        return self._model

    def transcribe(self, audio_path, on_progress, on_status, should_cancel) -> TranscriptionResult:
        model = self._load(on_status)
        on_status("Transcrevendo…")
        initial_prompt, hotwords = build_prompts(self.vocabulary)
        segments_iter, info = model.transcribe(
            read_wav(audio_path),
            language=self.language,
            beam_size=5,
            vad_filter=True,
            vad_parameters=VAD_PARAMETERS,
            initial_prompt=initial_prompt,
            hotwords=hotwords,
            # Sem herdar o texto anterior: evita os laços de repetição típicos de áudio longo.
            condition_on_previous_text=False,
            repetition_penalty=1.05,
        )
        total = info.duration or 1.0
        segments: list[Segment] = []
        for seg in segments_iter:
            if should_cancel():
                raise TranscriptionCancelled()
            text = seg.text.strip()
            if text:
                segments.append(Segment(start=round(seg.start, 2), end=round(seg.end, 2), text=text))
            on_progress(min(seg.end / total, 1.0))
        on_progress(1.0)
        return TranscriptionResult(segments=clean_segments(segments), language=info.language, duration=info.duration)
