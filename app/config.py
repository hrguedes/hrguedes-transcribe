import os
import sys
from pathlib import Path

APP_NAME = "Transcribe"

SAMPLE_RATE = 16_000

WHISPER_MODEL = os.environ.get("TRANSCRIBE_MODEL", "small")
LANGUAGE = os.environ.get("TRANSCRIBE_LANGUAGE", "pt")


def app_data_dir() -> Path:
    override = os.environ.get("TRANSCRIBE_HOME")
    if override:
        base = Path(override)
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / APP_NAME
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home())) / APP_NAME
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


def sessions_dir() -> Path:
    path = app_data_dir() / "sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def models_dir() -> Path:
    path = app_data_dir() / "models"
    path.mkdir(parents=True, exist_ok=True)
    return path
