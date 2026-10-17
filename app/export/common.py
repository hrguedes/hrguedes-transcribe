from __future__ import annotations

from dataclasses import dataclass

from app.sessions.model import Segment, Session

PARAGRAPH_GAP_S = 1.5


def format_timestamp(seconds: float) -> str:
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def format_duration(seconds: float) -> str:
    total = round(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}min"
    if m:
        return f"{m}min {s:02d}s"
    return f"{s}s"


def format_date(session: Session) -> str:
    return f"{session.created_datetime:%d/%m/%Y %H:%M}"


@dataclass
class Paragraph:
    start: float
    text: str


def build_paragraphs(segments: list[Segment]) -> list[Paragraph]:
    """Agrupa segmentos em parágrafos, quebrando nas pausas mais longas da fala."""
    paragraphs: list[Paragraph] = []
    current: list[str] = []
    start = 0.0
    prev_end: float | None = None
    for seg in segments:
        if current and prev_end is not None and seg.start - prev_end >= PARAGRAPH_GAP_S:
            paragraphs.append(Paragraph(start, " ".join(current)))
            current = []
        if not current:
            start = seg.start
        current.append(seg.text)
        prev_end = seg.end
    if current:
        paragraphs.append(Paragraph(start, " ".join(current)))
    return paragraphs
