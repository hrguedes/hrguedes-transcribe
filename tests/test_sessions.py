import wave

import pytest

from app.sessions import Segment, Session, SessionStatus
from app.sessions.model import InvalidTransition


def test_create_and_reload(store):
    s = store.create()
    assert s.meta_path.exists()
    loaded = Session.load(s.path)
    assert loaded.id == s.id
    assert loaded.status is SessionStatus.IDLE


def test_state_machine(store):
    s = store.create()
    for status in ["recording", "paused", "recording", "stopped", "transcribing", "done", "transcribing"]:
        s.transition(SessionStatus(status))
    with pytest.raises(InvalidTransition):
        s.transition(SessionStatus.RECORDING)


def test_transcript_roundtrip_keeps_accents(store):
    s = store.create()
    segs = [Segment(0.0, 1.5, "Reunião de alinhamento"), Segment(2.0, 3.0, "Ação: revisar orçamento")]
    s.save_transcript(segs, "pt", "test")
    assert Session.load(s.path).load_transcript() == segs
    assert "Reunião" in s.transcript_path.read_text(encoding="utf-8")


def test_recover_interrupted(store):
    s = store.create()
    s.transition(SessionStatus.RECORDING)
    with wave.open(str(s.audio_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 32000)
    empty = store.create()

    recovered = store.recover_interrupted()

    assert [r.id for r in recovered] == [s.id]
    reloaded = Session.load(s.path)
    assert reloaded.status is SessionStatus.STOPPED
    assert reloaded.duration == pytest.approx(2.0)
    assert not empty.path.exists()
