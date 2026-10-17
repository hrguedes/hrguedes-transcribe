import time
import wave

import numpy as np
import pytest

from app.audio.capture import LinearResampler
from app.audio.mixed import MAX_DRIFT_SAMPLES, TrackMixer
from app.audio.recorder import RecorderThread
from app.audio.source import AudioSource


def test_loopback_detection():
    from app.audio.source import AudioDevice

    names = ["BlackHole 2ch", "Mixagem estéreo (Realtek(R) Audio)", "Stereo Mix (Realtek)", "CABLE Output (VB-Audio)"]
    assert all(AudioDevice(0, n, 2, 48000).is_loopback for n in names)
    assert not AudioDevice(0, "Microfone (MacBook Pro)", 1, 48000).is_loopback
    assert AudioDevice(0, "Mic", 1, 48000, hostapi="Windows WASAPI").is_wasapi


def test_resampler_chunked_matches_rate():
    r = LinearResampler(48000, 16000)
    x = np.sin(np.linspace(0, 200, 48000)).astype(np.float32)
    out = np.concatenate([r.process(c) for c in np.array_split(x, 37)])
    assert abs(len(out) - 16000) <= 1
    assert out.dtype == np.float32


def test_mixer_sums_and_clips():
    m = TrackMixer()
    out = m.push(np.full(100, 0.7, np.float32), np.full(60, 0.7, np.float32))
    assert len(out) == 60
    assert out.max() == pytest.approx(1.0)
    rest = m.push(np.zeros(0, np.float32), np.zeros(40, np.float32))
    assert len(rest) == 40
    assert rest[0] == pytest.approx(0.7)


def test_mixer_pads_stalled_track():
    m = TrackMixer()
    out = m.push(np.full(MAX_DRIFT_SAMPLES + 1, 0.1, np.float32), np.zeros(0, np.float32))
    assert len(out) == MAX_DRIFT_SAMPLES + 1


class FakeSource(AudioSource):
    """Gera 16 kHz em tempo real, como um microfone."""

    def __init__(self):
        self._t0 = None
        self._emitted = 0
        self._err = None

    def start(self):
        self._t0 = time.monotonic()

    def read(self):
        due = int((time.monotonic() - self._t0) * 16000)
        n, self._emitted = due - self._emitted, due
        return np.full(n, 0.25, np.float32)

    def stop(self):
        pass

    @property
    def error(self):
        return self._err


def test_recorder_pause_drops_frames(qapp, tmp_path):
    src = FakeSource()
    src.start()
    path = tmp_path / "a.wav"
    rec = RecorderThread(src, path)
    rec.start()
    time.sleep(0.5)
    rec.pause()
    time.sleep(0.5)
    rec.resume()
    time.sleep(0.5)
    rec.request_stop()
    rec.wait()

    with wave.open(str(path), "rb") as wf:
        assert wf.getframerate() == 16000
        assert wf.getnchannels() == 1
        seconds = wf.getnframes() / 16000
    assert seconds == pytest.approx(rec.seconds_written)
    assert 0.8 < seconds < 1.25


def test_recorder_reports_device_loss(qapp, tmp_path):
    src = FakeSource()
    src.start()
    rec = RecorderThread(src, tmp_path / "a.wav")
    errors = []
    rec.failed.connect(errors.append)
    rec.start()
    time.sleep(0.2)
    src._err = "Microfone foi desconectado"
    rec.wait(2000)
    qapp.processEvents()
    assert errors == ["Microfone foi desconectado"]
