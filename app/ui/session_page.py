from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.controller import AppController
from app.export import FORMATS, export_session
from app.export.common import build_paragraphs, format_date, format_duration, format_timestamp
from app.sessions import Session, SessionStatus
from app.sessions.model import STATUS_LABELS


class SessionPage(QWidget):
    def __init__(self, controller: AppController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.session: Session | None = None

        self.title_label = QLabel(objectName="pageTitle", wordWrap=True)
        self.meta_label = QLabel(objectName="muted")
        self.error_label = QLabel(objectName="warning", wordWrap=True)

        self.progress_status = QLabel(objectName="muted")
        self.progress_bar = QProgressBar(maximum=1000, textVisible=False)
        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.clicked.connect(self._cancel)
        progress_row = QHBoxLayout()
        progress_row.addWidget(self.progress_bar, 1)
        progress_row.addWidget(self.cancel_btn)
        self.progress_box = QWidget()
        progress_layout = QVBoxLayout(self.progress_box)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.addWidget(self.progress_status)
        progress_layout.addLayout(progress_row)

        self.text = QPlainTextEdit(readOnly=True)
        self.text.setPlaceholderText("A transcrição aparece aqui quando terminar.")

        self.timestamps_cb = QCheckBox("Incluir timestamps")
        self.timestamps_cb.toggled.connect(self._render_text)
        self.transcribe_btn = QPushButton("Transcrever")
        self.transcribe_btn.clicked.connect(self._transcribe)
        self.save_btn = QPushButton("Salvar como…")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._save_as)

        actions = QHBoxLayout()
        actions.addWidget(self.timestamps_cb)
        actions.addStretch()
        actions.addWidget(self.transcribe_btn)
        actions.addWidget(self.save_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.addWidget(self.title_label)
        layout.addWidget(self.meta_label)
        layout.addWidget(self.error_label)
        layout.addWidget(self.progress_box)
        layout.addWidget(self.text, 1)
        layout.addLayout(actions)

        controller.session_changed.connect(self._on_session_changed)
        controller.transcription_progress.connect(self._on_progress)
        controller.transcription_status.connect(self._on_status)

    def show_session(self, session: Session) -> None:
        self.session = session
        self.progress_bar.setValue(0)
        self.progress_status.setText("")
        self._refresh()

    def _refresh(self) -> None:
        s = self.session
        if s is None:
            return
        queued = self.controller.is_queued(s.id)
        transcribing = s.status is SessionStatus.TRANSCRIBING
        status = "Na fila" if queued else STATUS_LABELS[s.status]
        if s.extra.get("recovered"):
            status += " · recuperada após encerramento inesperado"

        self.title_label.setText(s.title)
        meta = [format_date(s), format_duration(s.duration), status]
        if s.model and s.has_transcript:
            meta.append(f"modelo {s.model.removeprefix('faster-whisper-')}")
        self.meta_label.setText("  ·  ".join(meta))
        self.error_label.setText(s.error or "")
        self.error_label.setVisible(bool(s.error))
        self.progress_box.setVisible(transcribing or queued)
        self.cancel_btn.setText("Remover da fila" if queued else "Cancelar")

        busy = transcribing or queued or s.status in (SessionStatus.RECORDING, SessionStatus.PAUSED)
        self.transcribe_btn.setVisible(not busy and s.audio_path.exists())
        self.transcribe_btn.setText("Transcrever novamente" if s.has_transcript else "Transcrever")
        self.save_btn.setEnabled(s.has_transcript and not transcribing)
        self._render_text()

    def _render_text(self) -> None:
        s = self.session
        if s is None or not s.has_transcript:
            self.text.setPlainText("")
            return
        segments = s.load_transcript()
        if self.timestamps_cb.isChecked():
            body = "\n".join(f"[{format_timestamp(seg.start)}] {seg.text}" for seg in segments)
        else:
            body = "\n\n".join(p.text for p in build_paragraphs(segments))
        self.text.setPlainText(body or "(Nenhuma fala detectada.)")

    def _on_session_changed(self, session: Session) -> None:
        if self.session and session.id == self.session.id:
            self.session = session
            self._refresh()

    def _on_progress(self, session_id: str, fraction: float) -> None:
        if self.session and session_id == self.session.id:
            self.progress_bar.setValue(int(fraction * 1000))
            if fraction > 0:
                self.progress_status.setText(f"Transcrevendo… {fraction:.0%}")

    def _on_status(self, session_id: str, message: str) -> None:
        if self.session and session_id == self.session.id:
            self.progress_status.setText(message)

    def _cancel(self) -> None:
        if self.session:
            self.controller.cancel_transcription(self.session.id)
            self._refresh()

    def _transcribe(self) -> None:
        if self.session:
            self.controller.enqueue_transcription(self.session)
            self._refresh()

    def _save_as(self) -> None:
        s = self.session
        if s is None:
            return
        docs = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        safe_title = "".join(c if c.isalnum() or c in " -_" else "-" for c in s.title).strip()
        filters = ";;".join(FORMATS.values())
        path_str, selected = QFileDialog.getSaveFileName(
            self, "Salvar transcrição", str(Path(docs) / f"{safe_title}.pdf"), filters
        )
        if not path_str:
            return
        path = Path(path_str)
        fmt = path.suffix.lower().lstrip(".")
        if fmt not in FORMATS:
            fmt = next((k for k, v in FORMATS.items() if v == selected), "pdf")
            path = path.with_name(path.name + f".{fmt}")
        try:
            export_session(s, path, fmt, timestamps=self.timestamps_cb.isChecked())
        except OSError as exc:
            QMessageBox.critical(self, "Erro ao salvar", f"Não foi possível salvar o arquivo:\n{exc}")
