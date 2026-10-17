from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, QThread, Signal, Slot

from app.audio import AudioDevice, create_audio_source
from app.audio.recorder import RecorderThread
from app.sessions import Session, SessionStatus, SessionStore
from app.settings import Settings
from app.transcription import Transcriber, TranscriptionResult, create_transcriber
from app.transcription.worker import TranscriptionWorker

log = logging.getLogger(__name__)

MIN_AUDIO_SECONDS = 1.0


class AppController(QObject):
    recording_state_changed = Signal(object)  # SessionStatus: IDLE, RECORDING ou PAUSED
    level_changed = Signal(float)
    recording_finished = Signal(object)  # Session
    session_changed = Signal(object)  # Session
    transcription_progress = Signal(str, float)  # session_id, fração 0..1
    transcription_status = Signal(str, str)  # session_id, mensagem
    error = Signal(str)

    def __init__(
        self,
        store: SessionStore,
        settings: Settings | None = None,
        transcriber_factory: Callable[[Settings], Transcriber] = create_transcriber,
    ):
        super().__init__()
        self.store = store
        self.settings = settings or Settings()
        self._transcriber_factory = transcriber_factory
        self._transcriber: Transcriber | None = None

        self.recording_session: Session | None = None
        self._recorder: RecorderThread | None = None

        self.transcribing_session: Session | None = None
        self._queue: list[Session] = []
        self._tx_thread: QThread | None = None
        self._tx_worker: TranscriptionWorker | None = None

    # ---- gravação -------------------------------------------------------

    @property
    def recording_state(self) -> SessionStatus:
        return self.recording_session.status if self.recording_session else SessionStatus.IDLE

    def elapsed_seconds(self) -> float:
        return self._recorder.seconds_written if self._recorder else 0.0

    def start_recording(self, mic: AudioDevice | None, system: AudioDevice | None) -> None:
        """Lança `AudioSourceError` se nenhum dispositivo puder ser aberto."""
        if self._recorder is not None:
            return
        source = create_audio_source(mic, system)
        source.start()
        try:
            session = self.store.create()
            session.extra["devices"] = {
                "mic": mic.name if mic else None,
                "system": system.name if system else None,
            }
            session.transition(SessionStatus.RECORDING)
        except Exception:
            source.stop()
            raise

        recorder = RecorderThread(source, session.audio_path)
        recorder.level_changed.connect(self.level_changed)
        recorder.failed.connect(self._on_recorder_failed)
        self.recording_session = session
        self._recorder = recorder
        recorder.start()
        self.session_changed.emit(session)
        self.recording_state_changed.emit(SessionStatus.RECORDING)

    def toggle_pause(self) -> None:
        session, recorder = self.recording_session, self._recorder
        if session is None or recorder is None:
            return
        if session.status is SessionStatus.RECORDING:
            recorder.pause()
            session.transition(SessionStatus.PAUSED)
        else:
            recorder.resume()
            session.transition(SessionStatus.RECORDING)
        self.session_changed.emit(session)
        self.recording_state_changed.emit(session.status)

    def stop_recording(self, transcribe: bool = True) -> Session | None:
        session, recorder = self.recording_session, self._recorder
        if session is None or recorder is None:
            return None
        recorder.request_stop()
        recorder.wait()
        self._recorder = None
        self.recording_session = None

        session.duration = session.audio_duration()
        session.transition(SessionStatus.STOPPED)
        self.recording_state_changed.emit(SessionStatus.IDLE)

        if session.duration < MIN_AUDIO_SECONDS:
            session.fail("Gravação vazia: nenhum áudio foi capturado.")
        elif transcribe:
            self.enqueue_transcription(session)
        self.session_changed.emit(session)
        self.recording_finished.emit(session)
        return session

    @Slot(str)
    def _on_recorder_failed(self, message: str) -> None:
        self.error.emit(f"{message}. A gravação foi encerrada e o áudio capturado até aqui foi mantido.")
        self.stop_recording()

    # ---- transcrição ----------------------------------------------------

    def apply_settings(self, settings: Settings) -> None:
        """Vale a partir da próxima transcrição; a que está rodando não é afetada."""
        self.settings = settings

    def _transcriber_for_current_settings(self) -> Transcriber:
        if self._transcriber is None or self._transcriber.model_id != self.settings.model:
            self._transcriber = self._transcriber_factory(self.settings)
        self._transcriber.set_vocabulary(self.settings.vocabulary)
        return self._transcriber

    def is_model_available(self) -> bool:
        return self._transcriber_for_current_settings().is_available()

    @property
    def is_transcribing(self) -> bool:
        return self._tx_thread is not None

    def is_queued(self, session_id: str) -> bool:
        return any(s.id == session_id for s in self._queue)

    def enqueue_transcription(self, session: Session) -> None:
        busy_ids = {s.id for s in self._queue}
        if self.transcribing_session:
            busy_ids.add(self.transcribing_session.id)
        if session.id in busy_ids:
            return
        if self._tx_thread is None:
            self._start_transcription(session)
        else:
            self._queue.append(session)
            self.transcription_status.emit(session.id, "Na fila, aguardando outra transcrição terminar…")
            self.session_changed.emit(session)

    def cancel_transcription(self, session_id: str) -> None:
        if self.transcribing_session and self.transcribing_session.id == session_id and self._tx_worker:
            self.transcription_status.emit(session_id, "Cancelando…")
            self._tx_worker.cancel()
            return
        for queued in list(self._queue):
            if queued.id == session_id:
                self._queue.remove(queued)
                self.session_changed.emit(queued)

    def _start_transcription(self, session: Session) -> None:
        transcriber = self._transcriber_for_current_settings()
        session.transition(SessionStatus.TRANSCRIBING)
        self.transcribing_session = session

        thread = QThread()
        worker = TranscriptionWorker(transcriber, session.audio_path)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_tx_progress)
        worker.status.connect(self._on_tx_status)
        worker.finished.connect(self._on_tx_finished)
        worker.failed.connect(self._on_tx_failed)
        worker.cancelled.connect(self._on_tx_cancelled)
        self._tx_thread, self._tx_worker = thread, worker
        thread.start()
        self.session_changed.emit(session)
        self.transcription_progress.emit(session.id, 0.0)

    @Slot(float)
    def _on_tx_progress(self, fraction: float) -> None:
        if self.transcribing_session:
            self.transcription_progress.emit(self.transcribing_session.id, fraction)

    @Slot(str)
    def _on_tx_status(self, message: str) -> None:
        if self.transcribing_session:
            self.transcription_status.emit(self.transcribing_session.id, message)

    @Slot(object)
    def _on_tx_finished(self, result: TranscriptionResult) -> None:
        session = self.transcribing_session
        assert session is not None and self._transcriber is not None
        try:
            session.save_transcript(result.segments, result.language, self._transcriber.name)
            session.transition(SessionStatus.DONE)
        except OSError as exc:
            session.fail(f"Falha ao salvar a transcrição: {exc}")
            self.error.emit(session.error)
        self._finish_transcription()

    @Slot(str)
    def _on_tx_failed(self, message: str) -> None:
        session = self.transcribing_session
        assert session is not None
        log.error("Transcrição falhou (%s): %s", session.id, message)
        session.fail(message)
        self.error.emit(f"A transcrição falhou: {message}\nO áudio foi mantido; tente transcrever novamente.")
        self._finish_transcription()

    @Slot()
    def _on_tx_cancelled(self) -> None:
        session = self.transcribing_session
        assert session is not None
        session.transition(SessionStatus.STOPPED)
        self._finish_transcription()

    def _finish_transcription(self) -> None:
        session = self.transcribing_session
        thread, worker = self._tx_thread, self._tx_worker
        self.transcribing_session = None
        self._tx_thread = self._tx_worker = None
        if thread is not None:
            thread.quit()
            thread.wait()
        if worker is not None:
            worker.deleteLater()
        if thread is not None:
            thread.deleteLater()
        if session is not None:
            self.session_changed.emit(session)
        if self._queue:
            self._start_transcription(self._queue.pop(0))

    # ---- encerramento ---------------------------------------------------

    def shutdown(self) -> None:
        """Fecha sem perder nada: áudio fica salvo e a sessão volta a `stopped`."""
        self._queue.clear()
        self.stop_recording(transcribe=False)
        if self._tx_worker is not None:
            self._tx_worker.cancel()
            assert self._tx_thread is not None
            self._tx_thread.quit()
            self._tx_thread.wait(10_000)
            if self.transcribing_session:
                self.transcribing_session.status = SessionStatus.STOPPED
                self.transcribing_session.save_meta()
