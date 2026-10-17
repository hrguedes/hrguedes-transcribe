from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImageReader, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QWidget

from app.config import APP_NAME

_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))  # _MEIPASS: executável do PyInstaller
CREATOR_PHOTO = _ROOT / "imgs" / "creator.jpeg"
PHOTO_SIZE = 240

MESSAGE = "Seguinte, Gabriel: esse cara transcreve os textos para você de graça, pai."


def circular_pixmap(path: Path, size: int, device_pixel_ratio: float) -> QPixmap | None:
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)  # aplica a rotação EXIF das fotos de celular
    image = reader.read()
    if image.isNull():
        return None
    src = QPixmap.fromImage(image)
    px = round(size * device_pixel_ratio)
    src = src.scaled(px, px, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
    # Recorte quadrado um pouco acima do centro: em retratos o rosto fica no terço superior.
    x = (src.width() - px) // 2
    y = (src.height() - px) // 3
    src = src.copy(x, y, px, px)

    out = QPixmap(px, px)
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip = QPainterPath()
    clip.addEllipse(QRectF(0, 0, px, px))
    painter.setClipPath(clip)
    painter.drawPixmap(0, 0, src)
    painter.end()
    out.setDevicePixelRatio(device_pixel_ratio)
    return out


class WelcomeDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(APP_NAME)
        self.setFixedSize(460, 560)
        self.setStyleSheet("""
            QLabel#welcomeTitle { font-size: 34px; font-weight: 700; }
            QLabel#welcomeMessage { font-size: 17px; color: #424242; }
            QPushButton#welcomeOk {
                background-color: #d32f2f; color: white; border: none; border-radius: 8px;
                font-size: 16px; font-weight: 600; padding: 10px 48px;
            }
            QPushButton#welcomeOk:hover { background-color: #b71c1c; }
        """)

        title = QLabel(APP_NAME, objectName="welcomeTitle", alignment=Qt.AlignmentFlag.AlignCenter)

        photo = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        pixmap = circular_pixmap(CREATOR_PHOTO, PHOTO_SIZE, self.devicePixelRatioF())
        if pixmap is not None:
            photo.setPixmap(pixmap)
        photo.setVisible(pixmap is not None)

        message = QLabel(MESSAGE, objectName="welcomeMessage", wordWrap=True, alignment=Qt.AlignmentFlag.AlignCenter)

        ok = QPushButton("OK", objectName="welcomeOk")
        ok.setCursor(Qt.CursorShape.PointingHandCursor)
        ok.setDefault(True)
        ok.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.addWidget(title)
        layout.addSpacing(20)
        layout.addWidget(photo)
        layout.addSpacing(20)
        layout.addWidget(message)
        layout.addStretch()
        layout.addWidget(ok, alignment=Qt.AlignmentFlag.AlignCenter)
