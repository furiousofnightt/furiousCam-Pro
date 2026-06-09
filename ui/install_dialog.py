"""
ui/install_dialog.py — Dialog to guide the user through installing OBS Virtual Camera.
"""
import subprocess
import sys
import os
import urllib.request
import threading

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QFrame
)
from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtGui import QFont, QDesktopServices, QIcon
import ui.icons as icons


# ── Download worker ──────────────────────────────────────────────
class DownloadWorker(QThread):
    progress = Signal(int)   # 0-100
    finished = Signal(str)   # path on success, empty string on error
    error = Signal(str)

    def __init__(self, url: str, dest: str):
        super().__init__()
        self.url = url
        self.dest = dest

    def run(self):
        try:
            def _reporthook(count, block_size, total_size):
                if total_size > 0:
                    pct = int(count * block_size * 100 / total_size)
                    self.progress.emit(min(pct, 99))

            urllib.request.urlretrieve(self.url, self.dest, _reporthook)
            self.progress.emit(100)
            self.finished.emit(self.dest)
        except Exception as e:
            self.error.emit(str(e))


# ── Install Dialog ───────────────────────────────────────────────
class VirtualCamInstallDialog(QDialog):
    """
    Guides the user to install OBS Virtual Camera.
    Offers:
    - One-click download + silent install of the OBS Virtual Camera standalone plugin
    - Or "Open OBS website" option for manual install
    """

    # Standalone OBS Virtual Camera installer (lightweight, ~15 MB)
    # This is the official OBS Studio release page. We open browser for safety.
    OBS_DOWNLOAD_URL = "https://obsproject.com/wiki/install-instructions/windows"
    OBS_PLUGIN_URL   = "https://github.com/obsproject/obs-studio/releases/latest"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Instalar Câmera Virtual")
        self.setFixedSize(480, 380)
        self.setModal(True)
        self._worker = None
        self._installer_path = None
        self._apply_style()
        self._build_ui()

    def _apply_style(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #0d0d10;
                color: #e0e0e0;
                font-family: 'Segoe UI', sans-serif;
            }
            QLabel { color: #c0c0d0; }
            QLabel#title { color: #00e676; font-size: 16px; font-weight: 800; }
            QLabel#subtitle { color: #888; font-size: 11px; }
            QLabel#step { color: #aaa; font-size: 11px; }
            QPushButton#primary {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00c853, stop:1 #00e676);
                color: #000;
                border: none; border-radius: 8px;
                padding: 12px 24px;
                font-size: 13px; font-weight: 700;
            }
            QPushButton#primary:hover { background: #00e676; }
            QPushButton#primary:disabled { background: #1a3d2a; color: #2d6b45; }
            QPushButton#secondary {
                background-color: #1a1a22;
                color: #90caf9;
                border: 1px solid #2a3a4a;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 12px;
            }
            QPushButton#secondary:hover { background-color: #1e2535; }
            QPushButton#close_btn {
                background-color: #1a1a22;
                color: #888;
                border: 1px solid #333;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 11px;
            }
            QProgressBar {
                background-color: #1a1a22;
                border: 1px solid #333;
                border-radius: 4px;
                height: 8px;
                text-align: center;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00c853, stop:1 #00e676);
                border-radius: 4px;
            }
            QFrame#divider { background: #1e1e26; max-height: 1px; border: none; }
        """)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(14)

        # Header
        lbl_icon = QLabel()
        lbl_icon.setPixmap(icons.get_icon(icons.SVG_CAST, "#00e676", 32).pixmap(32, 32))
        lbl_title = QLabel("Câmera Virtual não encontrada", objectName="title")
        lbl_subtitle = QLabel(
            "Para usar o FuriousCam Pro como webcam no OBS, Streamlabs, Discord\n"
            "ou Zoom, é necessário que o driver de Câmera Virtual esteja instalado.",
            objectName="subtitle"
        )
        lbl_subtitle.setWordWrap(True)

        layout.addWidget(lbl_icon)
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_subtitle)

        # Divider
        div = QFrame(objectName="divider")
        div.setFrameShape(QFrame.HLine)
        layout.addWidget(div)

        # Steps
        steps_frame = QFrame()
        steps_frame.setStyleSheet("background-color: #111116; border-radius: 8px; padding: 4px;")
        steps_layout = QVBoxLayout(steps_frame)
        steps_layout.setContentsMargins(16, 12, 16, 12)
        steps_layout.setSpacing(6)

        steps = [
            ("1.", "Instale o OBS Studio OU o Streamlabs Desktop"),
            ("2.", "Abra o programa instalado ao menos uma vez"),
            ("3.", "No OBS: Vídeo → Iniciar Câmera Virtual"),
            ("4.", "Reinicie o FuriousCam Pro e ative a Câmera Virtual"),
        ]
        for num, text in steps:
            row = QHBoxLayout()
            row.setSpacing(8)
            lbl_num = QLabel(num)
            lbl_num.setStyleSheet("color: #00e676; font-weight: 700; font-size: 11px;")
            lbl_num.setFixedWidth(20)
            lbl_text = QLabel(text, objectName="step")
            row.addWidget(lbl_num)
            row.addWidget(lbl_text)
            steps_layout.addLayout(row)

        layout.addWidget(steps_frame)

        # Note about Streamlabs
        lbl_note = QLabel(
            "O FuriousCam Pro suporta OBS Studio e Streamlabs automaticamente.\n"
            "Basta ter um dos dois instalados e aberto ao menos uma vez."
        )
        lbl_note.setStyleSheet("color: #555; font-size: 10px;")
        lbl_note.setWordWrap(True)
        layout.addWidget(lbl_note)

        # Progress bar (hidden until download)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        self.lbl_progress = QLabel("")
        self.lbl_progress.setStyleSheet("color: #666; font-size: 10px;")
        self.lbl_progress.setVisible(False)
        layout.addWidget(self.lbl_progress)

        layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_download = QPushButton(" Abrir Página de Download", objectName="primary")
        self.btn_download.setIcon(icons.get_icon(icons.SVG_MONITOR, "#000"))
        self.btn_download.clicked.connect(self._open_download_page)
        btn_row.addWidget(self.btn_download)

        btn_close = QPushButton("Fechar", objectName="close_btn")
        btn_close.clicked.connect(self.reject)
        btn_row.addWidget(btn_close)

        layout.addLayout(btn_row)

    def _open_download_page(self):
        """Opens the OBS Studio download page in the default browser."""
        QDesktopServices.openUrl(QUrl("https://obsproject.com/download"))
        self.lbl_progress.setVisible(True)
        self.lbl_progress.setText("Página aberta no navegador. Após instalar, reinicie o FuriousCam Pro.")
        self.lbl_progress.setStyleSheet("color: #00e676; font-size: 10px;")
        self.btn_download.setEnabled(False)
        self.btn_download.setText(" Página Aberta")

# ── Install VB-Cable Dialog ──────────────────────────────────────
class VBCableInstallDialog(QDialog):
    """
    Guides the user to install VB-Audio Virtual Cable.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Instalar Microfone Virtual (VB-Cable)")
        self.setFixedSize(480, 360)
        self.setModal(True)
        self._apply_style()
        self._build_ui()

    def _apply_style(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #0d0d10;
                color: #e0e0e0;
                font-family: 'Segoe UI', sans-serif;
            }
            QLabel { color: #c0c0d0; }
            QLabel#title { color: #00e676; font-size: 16px; font-weight: 800; }
            QLabel#subtitle { color: #888; font-size: 11px; }
            QLabel#step { color: #aaa; font-size: 11px; }
            QPushButton#primary {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00c853, stop:1 #00e676);
                color: #000;
                border: none; border-radius: 8px;
                padding: 12px 24px;
                font-size: 13px; font-weight: 700;
            }
            QPushButton#primary:hover { background: #00e676; }
            QPushButton#close_btn {
                background-color: #1a1a22;
                color: #888;
                border: 1px solid #333;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 11px;
            }
            QFrame#divider { background: #1e1e26; max-height: 1px; border: none; }
        """)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(14)

        # Header
        lbl_icon = QLabel()
        lbl_icon.setPixmap(icons.get_icon(icons.SVG_DOWNLOAD, "#00e676", 32).pixmap(32, 32))
        lbl_title = QLabel("Cabo de Áudio Virtual não encontrado", objectName="title")
        lbl_subtitle = QLabel(
            "Para que o OBS, Discord ou Zoom reconheçam o áudio do celular como\n"
            "um microfone real, você precisa instalar o VB-Audio Virtual Cable.",
            objectName="subtitle"
        )
        lbl_subtitle.setWordWrap(True)

        layout.addWidget(lbl_icon)
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_subtitle)

        # Divider
        div = QFrame(objectName="divider")
        div.setFrameShape(QFrame.HLine)
        layout.addWidget(div)

        # Steps
        steps_frame = QFrame()
        steps_frame.setStyleSheet("background-color: #111116; border-radius: 8px; padding: 4px;")
        steps_layout = QVBoxLayout(steps_frame)
        steps_layout.setContentsMargins(16, 12, 16, 12)
        steps_layout.setSpacing(6)

        steps = [
            ("1.", "Baixe o VB-Cable for Windows no site oficial"),
            ("2.", "Extraia o arquivo .zip em uma pasta"),
            ("3.", "Execute 'VBCABLE_Setup_x64.exe' como Administrador"),
            ("4.", "Reinicie o PC (ou apenas o FuriousCam Pro) e tente novamente"),
        ]
        for num, text in steps:
            row = QHBoxLayout()
            row.setSpacing(8)
            lbl_num = QLabel(num)
            lbl_num.setStyleSheet("color: #00e676; font-weight: 700; font-size: 11px;")
            lbl_num.setFixedWidth(20)
            lbl_text = QLabel(text, objectName="step")
            row.addWidget(lbl_num)
            row.addWidget(lbl_text)
            steps_layout.addLayout(row)

        layout.addWidget(steps_frame)
        
        self.lbl_progress = QLabel("")
        self.lbl_progress.setStyleSheet("color: #00e676; font-size: 10px;")
        self.lbl_progress.setVisible(False)
        layout.addWidget(self.lbl_progress)

        layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_download = QPushButton(" Abrir Site do VB-Cable", objectName="primary")
        self.btn_download.setIcon(icons.get_icon(icons.SVG_MONITOR, "#000"))
        self.btn_download.clicked.connect(self._open_download_page)
        btn_row.addWidget(self.btn_download)

        btn_close = QPushButton("Fechar", objectName="close_btn")
        btn_close.clicked.connect(self.reject)
        btn_row.addWidget(btn_close)

        layout.addLayout(btn_row)

    def _open_download_page(self):
        """Opens the VB-Cable website."""
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl("https://vb-audio.com/Cable/"))
        self.lbl_progress.setVisible(True)
        self.lbl_progress.setText("Página aberta. Lembre-se de instalar como Administrador!")
        self.btn_download.setEnabled(False)
        self.btn_download.setText(" Página Aberta")
