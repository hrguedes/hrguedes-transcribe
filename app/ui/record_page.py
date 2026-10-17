from __future__ import annotations

import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.audio import AudioDevice, AudioSourceError
from app.audio import devices as audio_devices
from app.controller import AppController
from app.export.common import format_timestamp
from app.sessions import SessionStatus
from app.transcription import models
from app.ui.settings_dialog import SettingsDialog
from app.ui.style import IDLE_COLOR, PAUSED_COLOR, RECORDING_COLOR, record_button_style

RECORD_BUTTON_SIZE = 168

if sys.platform == "win32":
    LOOPBACK_HINT = (
        "“Mixagem estéreo” não encontrada: só o microfone será gravado. Para capturar o áudio da reunião, "
        "abra Painel de Controle › Som › Gravação, clique com o botão direito, marque "
        "<i>Mostrar dispositivos desabilitados</i> e ative a <i>Mixagem estéreo</i>."
    )
else:
    LOOPBACK_HINT = (
        "BlackHole não encontrado: só o microfone será gravado. Para capturar o áudio da reunião, "
        "instale com <code>brew install blackhole-2ch</code> e crie um "
        "<i>Dispositivo de Saída Múltipla</i> (alto-falantes + BlackHole) no app Configuração de Áudio e MIDI."
    )


class RecordPage(QWidget):
    def __init__(self, controller: AppController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self._devices: list[AudioDevice] = []

        self.mic_combo = QComboBox()
        self.system_combo = QComboBox()
        refresh_btn = QToolButton(text="Atualizar")
        refresh_btn.setToolTip("Procurar dispositivos de áudio novamente")
        refresh_btn.clicked.connect(self.reload_devices)
        self.refresh_btn = refresh_btn

        system_row = QHBoxLayout()
        system_row.addWidget(self.system_combo, 1)
        system_row.addWidget(refresh_btn)

        form = QFormLayout()
        form.addRow("Microfone:", self.mic_combo)
        form.addRow("Áudio do sistema:", system_row)

        self.blackhole_hint = QLabel(LOOPBACK_HINT, objectName="warning", wordWrap=True)
        self.blackhole_hint.setTextFormat(Qt.TextFormat.RichText)

        self.timer_label = QLabel("00:00:00", objectName="timer", alignment=Qt.AlignmentFlag.AlignCenter)
        self.status_label = QLabel("Pronto para gravar", objectName="muted", alignment=Qt.AlignmentFlag.AlignCenter)

        self.level_bar = QProgressBar(objectName="level", textVisible=False, maximum=100)
        self.level_bar.setFixedWidth(260)

        self.record_btn = QPushButton("Gravar")
        self.record_btn.setFixedSize(RECORD_BUTTON_SIZE, RECORD_BUTTON_SIZE)
        self.record_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.record_btn.clicked.connect(self._on_record_clicked)

        self.pause_btn = QPushButton("Pausar")
        self.pause_btn.setFixedSize(110, 44)
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(controller.toggle_pause)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.record_btn)
        buttons.addSpacing(24)
        buttons.addWidget(self.pause_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
        buttons.addStretch()

        level_row = QHBoxLayout()
        level_row.addStretch()
        level_row.addWidget(self.level_bar)
        level_row.addStretch()

        reminder = QLabel(
            "Avise os participantes de que a reunião está sendo gravada. "
            "Áudio e transcrição ficam apenas neste computador.",
            objectName="muted",
            wordWrap=True,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 32)
        layout.addLayout(form)
        layout.addWidget(self.blackhole_hint)
        layout.addStretch()
        layout.addWidget(self.timer_label)
        layout.addWidget(self.status_label)
        layout.addSpacing(20)
        layout.addLayout(buttons)
        layout.addSpacing(20)
        layout.addLayout(level_row)
        layout.addStretch()
        layout.addWidget(reminder)

        self._tick = QTimer(self, interval=200)
        self._tick.timeout.connect(self._update_timer)

        controller.recording_state_changed.connect(self._apply_state)
        controller.level_changed.connect(lambda v: self.level_bar.setValue(int(v * 100)))

        self.reload_devices()
        self._apply_state(SessionStatus.IDLE)

    # ---- dispositivos ---------------------------------------------------

    def reload_devices(self) -> None:
        if self.controller.recording_state is not SessionStatus.IDLE:
            return
        try:
            audio_devices.refresh()
            self._devices = audio_devices.list_input_devices()
        except Exception as exc:
            self._devices = []
            QMessageBox.warning(self, "Áudio", f"Não foi possível listar os dispositivos de áudio:\n{exc}")

        blackhole = audio_devices.find_loopback(self._devices)
        default_idx = audio_devices.default_input_index()
        mics = [d for d in self._devices if not d.is_loopback]

        self.mic_combo.clear()
        self.mic_combo.addItem("Nenhum", None)
        for d in mics:
            self.mic_combo.addItem(d.name, d)
        default_mic = next((i + 1 for i, d in enumerate(mics) if d.index == default_idx), 1 if mics else 0)
        self.mic_combo.setCurrentIndex(default_mic)

        self.system_combo.clear()
        self.system_combo.addItem("Nenhum", None)
        for d in self._devices:
            self.system_combo.addItem(d.name, d)
        if blackhole:
            self.system_combo.setCurrentIndex(self._devices.index(blackhole) + 1)

        self.blackhole_hint.setVisible(blackhole is None)

    # ---- gravação -------------------------------------------------------

    def _on_record_clicked(self) -> None:
        if self.controller.recording_state is SessionStatus.IDLE:
            if not self._confirm_model_available():
                return
            mic = self.mic_combo.currentData()
            system = self.system_combo.currentData()
            if mic is not None and system is not None and mic.index == system.index:
                system = None
            try:
                self.controller.start_recording(mic, system)
            except AudioSourceError as exc:
                QMessageBox.warning(self, "Não foi possível gravar", str(exc))
            except OSError as exc:
                QMessageBox.critical(self, "Não foi possível gravar", f"Erro ao criar a sessão em disco:\n{exc}")
        else:
            self.controller.stop_recording()

    def _confirm_model_available(self) -> bool:
        if self.controller.is_model_available():
            return True
        label = models.get_model_info(self.controller.settings.model).label
        box = QMessageBox(
            QMessageBox.Icon.Warning,
            "Modelo não encontrado",
            f"O modelo de transcrição <b>{label}</b> não está baixado neste computador.",
            parent=self,
        )
        box.setInformativeText(
            "Sem ele, a gravação será salva, mas não será transcrita ao terminar. "
            "Baixe o modelo em Configurações ou grave assim mesmo e transcreva depois."
        )
        settings_btn = box.addButton("Abrir Configurações", QMessageBox.ButtonRole.AcceptRole)
        record_btn = box.addButton("Gravar mesmo assim", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(settings_btn)
        box.exec()

        clicked = box.clickedButton()
        if clicked is record_btn:
            return True
        if clicked is settings_btn:
            SettingsDialog(self.controller, self.window()).exec()
            return self.controller.is_model_available()
        return False

    def _update_timer(self) -> None:
        self.timer_label.setText(format_timestamp(self.controller.elapsed_seconds()))

    def _apply_state(self, state: SessionStatus) -> None:
        idle = state is SessionStatus.IDLE
        for w in (self.mic_combo, self.system_combo, self.refresh_btn):
            w.setEnabled(idle)
        self.pause_btn.setEnabled(not idle)

        if state is SessionStatus.RECORDING:
            color, text, status = RECORDING_COLOR, "Parar", "Gravando…"
            self.pause_btn.setText("Pausar")
            self._tick.start()
        elif state is SessionStatus.PAUSED:
            color, text, status = PAUSED_COLOR, "Parar", "Pausado"
            self.pause_btn.setText("Continuar")
        else:
            color, text, status = IDLE_COLOR, "Gravar", "Pronto para gravar"
            self.pause_btn.setText("Pausar")
            self._tick.stop()
            self.level_bar.setValue(0)
            self.timer_label.setText("00:00:00")

        self.record_btn.setText(text)
        self.record_btn.setStyleSheet(record_button_style(color, RECORD_BUTTON_SIZE))
        self.timer_label.setStyleSheet(f"color: {color};" if not idle else "")
        self.status_label.setText(status)
