from __future__ import annotations

import sys

import sounddevice as sd

from app.audio.source import AudioDevice


def list_input_devices() -> list[AudioDevice]:
    hostapis = [h["name"] for h in sd.query_hostapis()]
    devices = []
    for index, info in enumerate(sd.query_devices()):
        if info["max_input_channels"] > 0:
            devices.append(
                AudioDevice(
                    index=index,
                    name=info["name"],
                    channels=info["max_input_channels"],
                    samplerate=info["default_samplerate"],
                    hostapi=hostapis[info["hostapi"]],
                )
            )
    if sys.platform == "win32":
        # O Windows lista o mesmo dispositivo uma vez por API (MME, DirectSound,
        # WASAPI, WDM-KS). Ficamos só com o WASAPI, que tem os nomes completos.
        wasapi = [d for d in devices if d.is_wasapi]
        devices = wasapi or devices
    return devices


def default_input_index() -> int | None:
    try:
        if sys.platform == "win32":
            for api in sd.query_hostapis():
                if "wasapi" in api["name"].lower() and api["default_input_device"] >= 0:
                    return api["default_input_device"]
        index = sd.default.device[0]
    except Exception:  # noqa: BLE001
        return None
    return index if isinstance(index, int) and index >= 0 else None


def find_loopback(devices: list[AudioDevice]) -> AudioDevice | None:
    return next((d for d in devices if d.is_loopback), None)


def refresh() -> None:
    """Faz o PortAudio enxergar dispositivos conectados depois que o app abriu."""
    sd._terminate()
    sd._initialize()
