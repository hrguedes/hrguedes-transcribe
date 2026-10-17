import os
import time

from PySide6.QtWidgets import QApplication

from app.config import sessions_dir
from app.controller import AppController
from app.sessions import SessionStatus, SessionStore
from app.ui.main_window import MainWindow

app = QApplication([])
store = SessionStore(sessions_dir())
c = AppController(store)
w = MainWindow(c)
w.resize(980, 640)
w.show()


def pump(seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.02)


out = os.environ["SHOTS"]
pump(0.3)
w.grab().save(f"{out}/1-idle.png")
w.record_page.record_btn.click()
pump(2.0)
w.grab().save(f"{out}/2-recording.png")
w.record_page.pause_btn.click()
pump(1.0)
w.grab().save(f"{out}/3-paused.png")
w.record_page.pause_btn.click()
pump(1.0)
w.record_page.record_btn.click()
pump(0.3)
s = w.session_page.session
print("após parar:", s.status, f"{s.duration:.2f}s")
end = time.monotonic() + 60
while s.status is SessionStatus.TRANSCRIBING and time.monotonic() < end:
    pump(0.1)
w.grab().save(f"{out}/4-session.png")
print("final:", s.status, s.error, s.load_transcript())
c.shutdown()
