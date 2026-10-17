from app.config import LANGUAGE, models_dir
from app.settings import Settings
from app.transcription.transcriber import (
    FasterWhisperTranscriber,
    ModelNotDownloaded,
    Transcriber,
    TranscriptionCancelled,
    TranscriptionResult,
)


def create_transcriber(settings: Settings) -> Transcriber:
    return FasterWhisperTranscriber(settings.model, models_dir(), language=LANGUAGE, vocabulary=settings.vocabulary)


__all__ = [
    "FasterWhisperTranscriber",
    "ModelNotDownloaded",
    "Transcriber",
    "TranscriptionCancelled",
    "TranscriptionResult",
    "create_transcriber",
]
