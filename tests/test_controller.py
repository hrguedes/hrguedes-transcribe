import time
import wave

from PySide6.QtCore import QCoreApplication

from app.controller import AppController
from app.sessions import Segment, SessionStatus
from app.settings import Settings
from app.transcription import Transcriber, TranscriptionCancelled, TranscriptionResult


class FakeTranscriber(Transcriber):
    name = "fake"

    def __init__(self, delay=0.0, model_id="small"):
        self.delay = delay
        self.model_id = model_id
        self.vocabulary = []

    def set_vocabulary(self, vocabulary):
        self.vocabulary = vocabulary

    def transcribe(self, audio_path, on_progress, on_status, should_cancel):
        on_status("Transcrevendo…")
        for i in range(5):
            time.sleep(self.delay)
            if should_cancel():
                raise TranscriptionCancelled()
            on_progress((i + 1) / 5)
        return TranscriptionResult([Segment(0, 1, "Olá, mundo")], "pt", 2.0)


def _stopped_session(store):
    s = store.create()
    s.transition(SessionStatus.RECORDING)
    with wave.open(str(s.audio_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 32000)
    s.duration = 2.0
    s.transition(SessionStatus.STOPPED)
    return s


def _wait_until(cond, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        QCoreApplication.processEvents()
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_transcription_queue_runs_in_order(qapp, store):
    c = AppController(store, transcriber_factory=lambda s: FakeTranscriber(0.01))
    a, b = _stopped_session(store), _stopped_session(store)
    progress = []
    c.transcription_progress.connect(lambda sid, f: progress.append((sid, f)))

    c.enqueue_transcription(a)
    c.enqueue_transcription(b)
    assert c.is_queued(b.id)
    assert _wait_until(lambda: a.status is SessionStatus.DONE and b.status is SessionStatus.DONE)

    assert b.load_transcript()[0].text == "Olá, mundo"
    assert (a.id, 1.0) in progress and (b.id, 1.0) in progress


def test_cancel_keeps_audio(qapp, store):
    c = AppController(store, transcriber_factory=lambda s: FakeTranscriber(0.2))
    s = _stopped_session(store)
    c.enqueue_transcription(s)
    c.cancel_transcription(s.id)
    assert _wait_until(lambda: c.transcribing_session is None)
    assert s.status is SessionStatus.STOPPED
    assert s.audio_path.exists()
    assert not s.has_transcript


def test_settings_change_swaps_model_and_vocabulary(qapp, store):
    created = []

    def factory(settings):
        created.append(FakeTranscriber(0.0, settings.model))
        return created[-1]

    c = AppController(store, Settings(model="small"), factory)
    s = _stopped_session(store)
    c.enqueue_transcription(s)
    assert _wait_until(lambda: s.status is SessionStatus.DONE)

    c.apply_settings(Settings(model="small", vocabulary=["IOB"]))
    c.enqueue_transcription(s)
    assert _wait_until(lambda: s.status is SessionStatus.DONE and not c.is_transcribing)
    assert len(created) == 1
    assert created[0].vocabulary == ["IOB"]

    c.apply_settings(Settings(model="large-v3-turbo"))
    c.enqueue_transcription(s)
    assert _wait_until(lambda: s.status is SessionStatus.DONE and not c.is_transcribing)
    assert [t.model_id for t in created] == ["small", "large-v3-turbo"]


def test_missing_model_fails_without_downloading(qapp, store, tmp_path):
    from app.transcription import FasterWhisperTranscriber

    c = AppController(
        store,
        Settings(model="large-v3"),
        lambda st: FasterWhisperTranscriber(st.model, tmp_path / "models"),
    )
    s = _stopped_session(store)
    c.enqueue_transcription(s)
    assert _wait_until(lambda: s.status is SessionStatus.ERROR)
    assert "não foi baixado" in s.error
    assert not (tmp_path / "models").exists()
