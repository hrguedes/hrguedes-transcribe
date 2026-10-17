from __future__ import annotations

import argparse
import logging
import signal
import sys

from app.config import APP_NAME, app_data_dir, models_dir, sessions_dir
from app.settings import load_settings

log = logging.getLogger(APP_NAME)


def download_model(model_id: str) -> int:
    from app.transcription import models

    def report(done: int, total: int) -> None:
        print(f"\r{done / 1e6:,.0f} / {total / 1e6:,.0f} MB", end="", flush=True)

    info = models.get_model_info(model_id)
    if models.is_downloaded(models_dir(), model_id):
        print(f"O modelo {info.label} já está baixado.")
        return 0
    print(f"Baixando {info.label} (~{info.size_label})…")
    path = models.download(models_dir(), model_id, report)
    print(f"\nModelo disponível em {path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="transcribe", description=APP_NAME)
    parser.add_argument(
        "--download-model",
        nargs="?",
        const="",
        metavar="MODELO",
        help="baixa o modelo (padrão: o das configurações) e sai",
    )
    args, qt_args = parser.parse_known_args()

    log_format = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    if sys.stderr is None:
        # Executável sem console (PyInstaller --windowed): não há terminal para os logs.
        logging.basicConfig(level=logging.INFO, format=log_format, filename=app_data_dir() / "app.log", encoding="utf-8")
    else:
        logging.basicConfig(level=logging.INFO, format=log_format)
    settings = load_settings()

    if args.download_model is not None:
        return download_model(args.download_model or settings.model)

    from PySide6.QtCore import QLibraryInfo, QLocale, QTimer, QTranslator
    from PySide6.QtWidgets import QApplication, QDialog

    from app.controller import AppController
    from app.sessions import SessionStore
    from app.ui.main_window import MainWindow
    from app.ui.welcome import WelcomeDialog

    app = QApplication([sys.argv[0], *qt_args])
    app.setApplicationName(APP_NAME)

    QLocale.setDefault(QLocale("pt_BR"))
    translator = QTranslator(app)
    if translator.load("qtbase_pt_BR", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)

    store = SessionStore(sessions_dir())
    recovered = store.recover_interrupted()
    if recovered:
        log.info("Sessões recuperadas: %s", ", ".join(s.id for s in recovered))

    # Ctrl+C no terminal: o loop do Qt não deixa o Python tratar o sinal sozinho,
    # então um timer devolve o controle ao interpretador periodicamente.
    signal.signal(signal.SIGINT, lambda *_: app.closeAllWindows())
    sigint_timer = QTimer(interval=250)
    sigint_timer.timeout.connect(lambda: None)
    sigint_timer.start()

    if WelcomeDialog().exec() != QDialog.DialogCode.Accepted:
        return 0

    controller = AppController(store, settings)
    window = MainWindow(controller)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
