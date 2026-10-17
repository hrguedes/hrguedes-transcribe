from __future__ import annotations

import re
import unicodedata

from app.sessions.model import Segment

# Frases que o Whisper inventa em trechos de silêncio/ruído (vêm de legendas de vídeo
# usadas no treino). Comparadas sem acento, caixa e pontuação.
HALLUCINATIONS = (
    "legendas pela comunidade amara.org",
    "legenda por",
    "legendado por",
    "obrigado por assistir",
    "obrigada por assistir",
    "inscreva-se no canal",
    "se inscreva no canal",
    "nao se esqueca de se inscrever",
    "deixe seu like",
    "ate o proximo video",
)


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^\w\s.\-,]", "", text).strip(" .!?…")


def _is_hallucination(text: str) -> bool:
    norm = _normalize(text)
    return any(norm.startswith(h) for h in HALLUCINATIONS)


def clean_segments(segments: list[Segment]) -> list[Segment]:
    """Remove alucinações conhecidas e repetições consecutivas do mesmo texto."""
    cleaned: list[Segment] = []
    for seg in segments:
        if _is_hallucination(seg.text):
            continue
        if cleaned and _normalize(cleaned[-1].text) == _normalize(seg.text):
            cleaned[-1] = Segment(cleaned[-1].start, seg.end, cleaned[-1].text)
            continue
        cleaned.append(seg)
    return cleaned
