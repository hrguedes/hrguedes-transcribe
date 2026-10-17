from __future__ import annotations

import queue

import numpy as np
import sounddevice as sd

from app.audio.source import AudioDevice, AudioSourceError
from app.config import SAMPLE_RATE


class LinearResampler:
    """Reamostragem linear com estado entre blocos (fallback quando o driver não converte)."""

    def __init__(self, src_rate: float, dst_rate: float) -> None:
        self.ratio = src_rate / dst_rate
        self._pos = 0.0
        self._tail = np.zeros(0, dtype=np.float32)

    def process(self, x: np.ndarray) -> np.ndarray:
        if self.ratio == 1.0:
            return x
        buf = np.concatenate([self._tail, x])
        last = len(buf) - 1
        if last < self._pos:
            self._tail = buf
            return np.zeros(0, dtype=np.float32)
        n_out = int((last - self._pos) // self.ratio) + 1
        idx = self._pos + np.arange(n_out) * self.ratio
        out = np.interp(idx, np.arange(len(buf)), buf).astype(np.float32)
        next_pos = self._pos + n_out * self.ratio
        keep_from = min(int(next_pos), len(buf))
        self._tail = buf[keep_from:]
        self._pos = next_pos - keep_from
        return out


class StreamCapture:
    """Um dispositivo de entrada do sounddevice convertido para mono 16 kHz."""

    def __init__(self, device: AudioDevice, label: str) -> None:
        self.device = device
        self.label = label
        self.error: str | None = None
        self._queue: queue.SimpleQueue[np.ndarray] = queue.SimpleQueue()
        self._stream: sd.InputStream | None = None
        self._resampler: LinearResampler | None = None
        self._stopping = False

    def start(self) -> None:
        channels = min(2, self.device.channels)
        # CoreAudio (e o WASAPI com auto_convert) convertem a taxa de amostragem com boa
        # qualidade; só caímos no resampler próprio se o driver recusar 16 kHz.
        extra = sd.WasapiSettings(auto_convert=True) if self.device.is_wasapi else None
        rate: float = SAMPLE_RATE
        try:
            sd.check_input_settings(
                device=self.device.index, channels=channels, samplerate=rate, dtype="float32", extra_settings=extra
            )
        except Exception:  # noqa: BLE001
            rate = self.device.samplerate
            self._resampler = LinearResampler(rate, SAMPLE_RATE)
        try:
            self._stream = sd.InputStream(
                device=self.device.index,
                channels=channels,
                samplerate=rate,
                dtype="float32",
                blocksize=0,
                callback=self._callback,
                finished_callback=self._finished,
                extra_settings=extra,
            )
            self._stream.start()
        except Exception as exc:
            self._stream = None
            raise AudioSourceError(f"Não foi possível abrir {self.label} ({self.device.name}): {exc}") from exc

    def _callback(self, indata: np.ndarray, frames: int, time, status) -> None:
        mono = indata.mean(axis=1) if indata.shape[1] > 1 else indata[:, 0]
        self._queue.put(mono.copy())

    def _finished(self) -> None:
        if not self._stopping:
            self.error = f"{self.label} ({self.device.name}) foi desconectado"

    def read(self) -> np.ndarray:
        chunks = []
        while True:
            try:
                chunks.append(self._queue.get_nowait())
            except queue.Empty:
                break
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        data = np.concatenate(chunks)
        return self._resampler.process(data) if self._resampler else data

    def stop(self) -> None:
        self._stopping = True
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None
