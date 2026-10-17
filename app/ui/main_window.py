from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import APP_NAME
from app.controller import AppController
from app.export.common import format_duration
from app.sessions import Session, SessionStatus
from app.sessions.model import STATUS_LABELS
from app.ui.record_page import RecordPage
from app.ui.session_page import SessionPage
from app.ui.settings_dialog import SettingsDialog
from app.ui.style import APP_STYLE

SESSION_ID_ROLE = Qt.ItemDataRole.UserRole


class MainWindow(QMainWindow):
    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        self.setWindowTitle(APP_NAME)
        self.resize(980, 640)
        self.setStyleSheet(APP_STYLE)

        self.new_btn = QPushButton("Nova gravação")
        self.new_btn.clicked.connect(self.show_record_page)
        self.session_list = QListWidget(objectName="sessionList")
        self.session_list.itemClicked.connect(self._on_item_clicked)

        sidebar = QWidget()
        sidebar.setMinimumWidth(220)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(8, 8, 0, 8)
        self.settings_btn = QPushButton("Configurações")
        self.settings_btn.clicked.connect(self.open_settings)
        side_layout.addWidget(self.new_btn)
        side_layout.addWidget(self.session_list, 1)
        side_layout.addWidget(self.settings_btn)

        self.record_page = RecordPage(controller)
        self.session_page = SessionPage(controller)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.record_page)
        self.stack.addWidget(self.session_page)

        splitter = QSplitter()
        splitter.addWidget(sidebar)
        splitter.addWidget(self.stack)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 720])
        self.setCentralWidget(splitter)

        controller.session_changed.connect(self._on_session_changed)
        controller.recording_state_changed.connect(self._on_recording_state)
        controller.recording_finished.connect(self.show_session)
        controller.error.connect(lambda msg: QMessageBox.warning(self, APP_NAME, msg))

        self.reload_sessions()

    # ---- lista de sessões ----------------------------------------------

    def _item_text(self, s: Session) -> str:
        status = "Na fila" if self.controller.is_queued(s.id) else STATUS_LABELS[s.status]
        details = status if s.status in (SessionStatus.RECORDING, SessionStatus.PAUSED) else (
            f"{format_duration(s.duration)} · {status}"
        )
        return f"{s.title}\n{details}"

    def reload_sessions(self) -> None:
        selected = self._selected_id()
        self.session_list.clear()
        for s in self.controller.store.list():
            item = QListWidgetItem(self._item_text(s))
            item.setData(SESSION_ID_ROLE, s.id)
            self.session_list.addItem(item)
            if s.id == selected:
                item.setSelected(True)

    def _selected_id(self) -> str | None:
        items = self.session_list.selectedItems()
        return items[0].data(SESSION_ID_ROLE) if items else None

    def _find_item(self, session_id: str) -> QListWidgetItem | None:
        for i in range(self.session_list.count()):
            item = self.session_list.item(i)
            if item.data(SESSION_ID_ROLE) == session_id:
                return item
        return None

    def _on_session_changed(self, session: Session) -> None:
        item = self._find_item(session.id)
        if item is None:
            self.reload_sessions()
        else:
            item.setText(self._item_text(session))

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        session_id = item.data(SESSION_ID_ROLE)
        recording = self.controller.recording_session
        if recording and recording.id == session_id:
            self.show_record_page()
            return
        session = next((s for s in self.controller.store.list() if s.id == session_id), None)
        if session is None:
            self.reload_sessions()
            return
        if self.controller.transcribing_session and self.controller.transcribing_session.id == session_id:
            session = self.controller.transcribing_session
        self.session_page.show_session(session)
        self.stack.setCurrentWidget(self.session_page)

    # ---- navegação -----------------------------------------------------

    def show_record_page(self) -> None:
        self.session_list.clearSelection()
        recording = self.controller.recording_session
        if recording and (item := self._find_item(recording.id)):
            item.setSelected(True)
        self.stack.setCurrentWidget(self.record_page)

    def _on_recording_state(self, state: SessionStatus) -> None:
        recording = self.controller.recording_session
        if recording and (item := self._find_item(recording.id)):
            self.session_list.clearSelection()
            item.setSelected(True)

    def show_session(self, session: Session) -> None:
        if item := self._find_item(session.id):
            self.session_list.clearSelection()
            item.setSelected(True)
        self.session_page.show_session(session)
        self.stack.setCurrentWidget(self.session_page)

    def open_settings(self) -> None:
        SettingsDialog(self.controller, self).exec()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.controller.recording_state is not SessionStatus.IDLE:
            answer = QMessageBox.question(
                self,
                APP_NAME,
                "Há uma gravação em andamento. Encerrar e sair? O áudio gravado será mantido.",
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self.controller.shutdown()
        event.accept()
