from __future__ import annotations

import html
from pathlib import Path

from app.export.common import build_paragraphs, format_date, format_duration, format_timestamp
from app.sessions.model import Segment, Session

FORMATS = {
    "pdf": "PDF (*.pdf)",
    "txt": "Texto (*.txt)",
    "md": "Markdown (*.md)",
}


def to_txt(session: Session, segments: list[Segment], timestamps: bool = False) -> str:
    if timestamps:
        body = "\n".join(f"[{format_timestamp(s.start)}] {s.text}" for s in segments)
    else:
        body = "\n\n".join(p.text for p in build_paragraphs(segments))
    return body + "\n"


def to_md(session: Session, segments: list[Segment], timestamps: bool = False) -> str:
    lines = [
        f"# {session.title}",
        "",
        f"- **Data:** {format_date(session)}",
        f"- **Duração:** {format_duration(session.duration)}",
        "",
        "## Transcrição",
        "",
    ]
    for p in build_paragraphs(segments):
        prefix = f"**[{format_timestamp(p.start)}]** " if timestamps else ""
        lines += [prefix + p.text, ""]
    return "\n".join(lines)


def to_html(session: Session, segments: list[Segment], timestamps: bool = False) -> str:
    e = html.escape
    parts = [
        f"<h1>{e(session.title)}</h1>",
        (
            f"<p style='color:#555'><b>Data:</b> {e(format_date(session))} &nbsp;&nbsp; "
            f"<b>Duração:</b> {e(format_duration(session.duration))}</p>"
        ),
        "<hr/>",
    ]
    for p in build_paragraphs(segments):
        ts = f"<span style='color:#888'>[{format_timestamp(p.start)}]</span> " if timestamps else ""
        parts.append(f"<p>{ts}{e(p.text)}</p>")
    return "<html><body style='font-size:11pt'>" + "".join(parts) + "</body></html>"


def write_pdf(session: Session, segments: list[Segment], path: Path, timestamps: bool = False) -> None:
    from PySide6.QtCore import QMarginsF
    from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument

    writer = QPdfWriter(str(path))
    writer.setTitle(session.title)
    writer.setCreator("Transcribe")
    writer.setPageLayout(
        QPageLayout(
            QPageSize(QPageSize.PageSizeId.A4),
            QPageLayout.Orientation.Portrait,
            QMarginsF(20, 20, 20, 20),
            QPageLayout.Unit.Millimeter,
        )
    )
    doc = QTextDocument()
    doc.setHtml(to_html(session, segments, timestamps))
    doc.print_(writer)


def export_session(session: Session, path: Path, fmt: str, timestamps: bool = False) -> None:
    segments = session.load_transcript()
    if fmt == "pdf":
        write_pdf(session, segments, path, timestamps)
    elif fmt == "txt":
        path.write_text(to_txt(session, segments, timestamps), encoding="utf-8")
    elif fmt == "md":
        path.write_text(to_md(session, segments, timestamps), encoding="utf-8")
    else:
        raise ValueError(f"Formato desconhecido: {fmt}")
