from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.config import models_dir
from app.controller import AppController
from app.settings import Settings, save_settings
from app.transcription import models


class DownloadWorker(QObject):
    progress = Signal(int, int)
    finished = Signal()
    failed = Signal(str)

    def __init__(self, model_id: str) -> None:
        super().__init__()
        self.model_id = model_id

    @Slot()
    def run(self) -> None:
        try:
            models.download(models_dir(), self.model_id, self.progress.emit)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc) or type(exc).__name__)
        else:
            self.finished.emit()


class SettingsDialog(QDialog):
    def __init__(self, controller: AppController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Configurações de transcrição")
        self.setMinimumWidth(560)
        self._thread: QThread | None = None
        self._worker: DownloadWorker | None = None

        self.model_combo = QComboBox()
        self.model_combo.currentIndexChanged.connect(self._refresh_model_state)
        self.model_desc = QLabel(objectName="muted", wordWrap=True)
        self.model_state = QLabel(wordWrap=True)
        self.download_btn = QPushButton("Baixar")
        self.download_btn.clicked.connect(self._download)
        self.delete_btn = QPushButton("Remover do disco")
        self.delete_btn.clicked.connect(self._delete)
        self.download_bar = QProgressBar(maximum=1000)
        self.download_bar.setVisible(False)

        model_actions = QHBoxLayout()
        model_actions.addWidget(self.model_state, 1)
        model_actions.addWidget(self.delete_btn)
        model_actions.addWidget(self.download_btn)

        model_box = QGroupBox("Modelo")
        model_layout = QVBoxLayout(model_box)
        model_layout.addWidget(self.model_combo)
        model_layout.addWidget(self.model_desc)
        model_layout.addLayout(model_actions)
        model_layout.addWidget(self.download_bar)

        self.vocab_edit = QPlainTextEdit()
        self.vocab_edit.setPlaceholderText("Ex.:\nHugo Guedes\nIOB\nKubernetes\nOKR")
        self.vocab_edit.setPlainText("\n".join(controller.settings.vocabulary))
        vocab_box = QGroupBox("Vocabulário")
        vocab_layout = QVBoxLayout(vocab_box)
        vocab_layout.addWidget(
            QLabel(
                "Nomes de pessoas, empresas, produtos e siglas que aparecem nas suas reuniões, "
                "um por linha. Ajuda o modelo a escrevê-los corretamente.",
                objectName="muted",
                wordWrap=True,
            )
        )
        vocab_layout.addWidget(self.vocab_edit)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self._save)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(model_box)
        layout.addWidget(vocab_box, 1)
        layout.addWidget(
            QLabel(
                "As alterações valem para as próximas transcrições. Use “Transcrever novamente” "
                "em uma sessão para aplicá-las a gravações antigas.",
                objectName="muted",
                wordWrap=True,
            )
        )
        layout.addWidget(self.buttons)

        self._populate_models()

    # ---- modelos --------------------------------------------------------

    def _selected(self) -> models.ModelInfo:
        return self.model_combo.currentData()

    def _populate_models(self) -> None:
        current = self.controller.settings.model
        catalog = list(models.CATALOG)
        if current not in {m.id for m in catalog}:
            catalog.append(models.get_model_info(current))
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for info in catalog:
            mark = "✓ baixado" if models.is_downloaded(models_dir(), info.id) else info.size_label
            self.model_combo.addItem(f"{info.label}  ({mark})", info)
            if info.id == current:
                self.model_combo.setCurrentIndex(self.model_combo.count() - 1)
        self.model_combo.blockSignals(False)
        self._refresh_model_state()

    def _refresh_model_state(self) -> None:
        info = self._selected()
        if info is None:
            return
        downloading = self._thread is not None
        downloaded = models.is_downloaded(models_dir(), info.id)
        in_use = self.controller.is_transcribing and self.controller.settings.model == info.id
        self.model_desc.setText(info.description)
        if downloading:
            self.model_state.setText(f"Baixando {info.label}…")
        elif downloaded:
            self.model_state.setText("Baixado e pronto para uso offline.")
        else:
            self.model_state.setText(f"Não baixado. Download de cerca de {info.size_label}, feito uma única vez.")
        self.download_btn.setVisible(not downloaded)
        self.download_btn.setEnabled(not downloading)
        self.delete_btn.setVisible(downloaded)
        self.delete_btn.setEnabled(not downloading and not in_use)
        self.model_combo.setEnabled(not downloading)
        self.buttons.setEnabled(not downloading)

    def _download(self) -> None:
        info = self._selected()
        answer = QMessageBox.question(
            self,
            "Baixar modelo",
            f"Baixar o modelo {info.label} (cerca de {info.size_label}) do Hugging Face?\n\n"
            "Só o modelo é baixado; nenhum áudio ou transcrição sai do computador.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.download_bar.setValue(0)
        self.download_bar.setVisible(True)
        thread = QThread(self)
        worker = DownloadWorker(info.id)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_download_progress)
        worker.finished.connect(self._on_download_finished)
        worker.failed.connect(self._on_download_failed)
        self._thread, self._worker = thread, worker
        thread.start()
        self._refresh_model_state()

    @Slot(int, int)
    def _on_download_progress(self, done: int, total: int) -> None:
        if total > 0:
            self.download_bar.setValue(min(999, int(done / total * 1000)))

    def _end_download(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
        self._thread = self._worker = None
        self.download_bar.setVisible(False)

    @Slot()
    def _on_download_finished(self) -> None:
        self._end_download()
        self._populate_models()

    @Slot(str)
    def _on_download_failed(self, message: str) -> None:
        self._end_download()
        self._refresh_model_state()
        QMessageBox.warning(
            self,
            "Download falhou",
            f"Não foi possível baixar o modelo:\n{message}\n\nO que já foi baixado é aproveitado na próxima tentativa.",
        )

    def _delete(self) -> None:
        info = self._selected()
        answer = QMessageBox.question(
            self, "Remover modelo", f"Apagar o modelo {info.label} do disco? Dá para baixá-lo de novo depois."
        )
        if answer == QMessageBox.StandardButton.Yes:
            models.delete_model(models_dir(), info.id)
            self._populate_models()

    # ---- salvar ---------------------------------------------------------

    def _save(self) -> None:
        info = self._selected()
        if not models.is_downloaded(models_dir(), info.id):
            answer = QMessageBox.question(
                self,
                "Modelo não baixado",
                f"O modelo {info.label} ainda não foi baixado, então as transcrições vão falhar até você baixá-lo. "
                "Salvar mesmo assim?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        settings = Settings(model=info.id, vocabulary=Settings.parse_vocabulary(self.vocab_edit.toPlainText()))
        try:
            save_settings(settings)
        except OSError as exc:
            QMessageBox.critical(self, "Erro", f"Não foi possível salvar as configurações:\n{exc}")
            return
        self.controller.apply_settings(settings)
        self.accept()

    def reject(self) -> None:
        if self._thread is None:
            super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._thread is not None:
            event.ignore()
        else:
            super().closeEvent(event)
