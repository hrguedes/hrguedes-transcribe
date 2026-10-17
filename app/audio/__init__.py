from app.audio.source import AudioDevice, AudioSource, AudioSourceError


def create_audio_source(mic: AudioDevice | None, system: AudioDevice | None) -> AudioSource:
    from app.audio.mixed import MixedInputSource

    return MixedInputSource(mic, system)


__all__ = ["AudioDevice", "AudioSource", "AudioSourceError", "create_audio_source"]
