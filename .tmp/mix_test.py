import subprocess
import time
from pathlib import Path

from PySide6.QtCore import QCoreApplication

from app.audio import create_audio_source, devices
from app.audio.recorder import RecorderThread
from app.transcription import create_transcriber

app = QCoreApplication([])
ds = devices.list_input_devices()
mic = next(d for d in ds if "MacBook" in d.name)
bh = devices.find_blackhole(ds)
src = create_audio_source(mic, bh)
src.start()
path = Path(".tmp/mix.wav")
rec = RecorderThread(src, path)
rec.start()
subprocess.run(
    ["say", "-v", "Luciana", "-a", "BlackHole 2ch",
     "Este áudio saiu pelo sistema. A gravação capturou a reunião pelo BlackHole."],
    check=True,
)
end = time.monotonic() + 0.5
while time.monotonic() < end:
    app.processEvents()
    time.sleep(0.02)
rec.request_stop()
rec.wait()
print(f"gravado: {rec.seconds_written:.2f}s")
r = create_transcriber().transcribe(path, lambda f: None, lambda m: None, lambda: False)
for s in r.segments:
    print(s)
