# PyInstaller: uv run --with pyinstaller pyinstaller transcribe.spec --noconfirm
# Gera dist/Transcribe/ (pasta com Transcribe.exe no Windows, Transcribe.app no macOS).
import sys

from PyInstaller.utils.hooks import collect_all

datas = [("imgs/creator.jpeg", "imgs")]
binaries = []
hiddenimports = []
# faster_whisper traz o modelo do VAD (assets/*.onnx); ctranslate2 traz DLLs nativas.
for package in ("faster_whisper", "ctranslate2"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

a = Analysis(
    ["run.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=[
        "tkinter",
        "pytest",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngineQuick",
    ],
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Transcribe",
    console=False,
    upx=False,
)

coll = COLLECT(exe, a.binaries, a.datas, name="Transcribe", upx=False)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Transcribe.app",
        bundle_identifier="com.hrguedes.transcribe",
        info_plist={
            "NSMicrophoneUsageDescription": "O Transcribe grava o áudio das suas reuniões para transcrevê-las localmente.",
            "NSHighResolutionCapable": True,
        },
    )
