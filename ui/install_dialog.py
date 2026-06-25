"""
ui/install_dialog.py — Dialogs para instalação de dependências de câmera virtual.
  - VirtualCamInstallDialog  : guia para OBS Studio ou Streamlabs
  - UnityCaptureInstallDialog: instala o driver Unity Capture bundled via regsvr32 elevado
  - VBCableInstallDialog     : guia para VB-Audio Virtual Cable
"""
import subprocess
import sys
import os
import ctypes
import threading
import logging

logger = logging.getLogger(__name__)

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, QThread, Signal, QUrl, QTimer
from PySide6.QtGui import QFont, QDesktopServices, QIcon
import ui.icons as icons


# ─────────────────────────────────────────────────────────────────
#  Detecção do driver Unity Capture via registro DirectShow
# ─────────────────────────────────────────────────────────────────
def is_unity_capture_installed() -> bool:
    """
    Verifica se o filtro DirectShow 'Unity Video Capture' está registrado
    no Windows. Pesquisa na categoria de video capture devices:
    HKLM\\SOFTWARE\\Classes\\CLSID\\{860BB310-5D01-11d0-BD3B-00A0C911CE86}\\Instance
    """
    try:
        import winreg
        # CLSID da categoria VideoInputDeviceCategory (DirectShow)
        video_cat = r"SOFTWARE\Classes\CLSID\{860BB310-5D01-11d0-BD3B-00A0C911CE86}\Instance"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, video_cat) as cat_key:
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(cat_key, i)
                    with winreg.OpenKey(cat_key, sub) as sk:
                        try:
                            name, _ = winreg.QueryValueEx(sk, "FriendlyName")
                            if "unity" in name.lower():
                                return True
                        except FileNotFoundError:
                            pass
                    i += 1
                except OSError:
                    break
        return False
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────
#  Worker: regsvr32 com elevação via ShellExecuteEx (UAC nativo)
# ─────────────────────────────────────────────────────────────────
class RegSvr32Worker(QThread):
    """
    Registra ou desregistra DLLs usando regsvr32 com elevação UAC.
    Usa ctypes.windll.shell32.ShellExecuteW com 'runas' para disparar
    o prompt de UAC de forma nativa, sem precisar de .bat externo.
    """
    finished = Signal(bool, str)   # success, message

    def __init__(self, dll_paths: list, unregister: bool = False):
        super().__init__()
        self.dll_paths = dll_paths
        self.unregister = unregister

    def run(self):
        import subprocess
        flag = "/u" if self.unregister else "/s"
        errors = []
        
        valid_dlls = [dll for dll in self.dll_paths if os.path.exists(dll)]
        if not valid_dlls:
            self.finished.emit(False, "Nenhuma DLL encontrada para registrar.")
            return

        # Encadeia os comandos com & para executar num único prompt de CMD elevado
        commands = [f'regsvr32 {flag} \\"{dll}\\"' for dll in valid_dlls]
        cmd_args = "/c " + " & ".join(commands)

        try:
            # Usa PowerShell para lançar o processo elevado e AGUARDAR (-Wait) a conclusão
            ps_command = f"Start-Process cmd -ArgumentList '{cmd_args}' -Verb RunAs -WindowStyle Hidden -Wait"
            
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_command],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode != 0:
                errors.append(f"O prompt de administrador foi cancelado ou falhou. (código {result.returncode})")
                logger.error(f"PowerShell falhou: {result.stderr}")
            else:
                logger.info(f"Comando elevado concluído com sucesso: {cmd_args}")
                
        except Exception as e:
            errors.append(str(e))
            logger.error(f"Exceção ao disparar UAC via PowerShell: {e}")

        if errors:
            self.finished.emit(False, "\n".join(errors))
        else:
            action = "desregistradas" if self.unregister else "registradas"
            self.finished.emit(True, f"DLLs {action} com sucesso.")


# ─────────────────────────────────────────────────────────────────
#  1. Dialog de Câmera Virtual (OBS / Streamlabs)
# ─────────────────────────────────────────────────────────────────
class VirtualCamInstallDialog(QDialog):
    """
    Apresenta ao usuário as instruções para obter a Câmera Virtual do OBS Studio.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Instalar Câmera Virtual")
        self.setFixedSize(520, 310)
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
            QLabel#title  { color: #00e676; font-size: 16px; font-weight: 800; }
            QLabel#subtitle { color: #888; font-size: 11px; }
            QLabel#step   { color: #aaa; font-size: 11px; }
            QLabel#card_title { color: #fff; font-size: 13px; font-weight: 700; }
            QLabel#card_sub   { color: #888; font-size: 10px; }
            QPushButton#primary {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00c853, stop:1 #00e676);
                color: #000;
                border: none; border-radius: 8px;
                padding: 10px 20px;
                font-size: 12px; font-weight: 700;
            }
            QPushButton#primary:hover { background: #00e676; }
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
            QFrame#divider { background: #1e1e26; max-height: 1px; border: none; }
            QFrame#card {
                background-color: #111116;
                border: 1px solid #1e1e2a;
                border-radius: 10px;
            }
        """)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 24)
        layout.setSpacing(14)

        # Header
        lbl_icon = QLabel()
        lbl_icon.setPixmap(icons.get_icon(icons.SVG_CAST, "#00e676", 32).pixmap(32, 32))
        lbl_title = QLabel("Câmera Virtual não encontrada", objectName="title")
        lbl_subtitle = QLabel(
            "Para a Câmera Virtual funcionar, instale o OBS Studio gratuitamente.\n"
            "Dica: Tendo o OBS instalado, o driver dele também aparecerá e\n"
            "poderá ser usado dentro do seu Streamlabs Desktop ou TikTok Live!",
            objectName="subtitle"
        )
        lbl_subtitle.setWordWrap(True)
        layout.addWidget(lbl_icon)
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_subtitle)

        div = QFrame(objectName="divider")
        div.setFrameShape(QFrame.HLine)
        layout.addWidget(div)

        # ── Card OBS Studio ──
        obs_card = self._make_card(
            icon_svg=icons.SVG_CAST,
            icon_color="#e74c3c",
            title="OBS Studio  ✦ Driver Oficial",
            subtitle="Recomendado. Instala o driver compatível com OBS e Streamlabs.",
            btn_text=" Abrir Site do OBS Studio",
            btn_color="#primary",
            on_click=lambda: self._open("https://obsproject.com/download", self.btn_obs)
        )
        self.btn_obs = obs_card.findChild(QPushButton)
        layout.addWidget(obs_card)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #00e676; font-size: 10px;")
        self.lbl_status.setVisible(False)
        layout.addWidget(self.lbl_status)

        layout.addStretch()

        # Fechar
        btn_close = QPushButton("Fechar", objectName="close_btn")
        btn_close.clicked.connect(self.reject)
        layout.addWidget(btn_close, alignment=Qt.AlignRight)

    def _make_card(self, icon_svg, icon_color, title, subtitle, btn_text, btn_color, on_click):
        card = QFrame(objectName="card")
        row = QHBoxLayout(card)
        row.setContentsMargins(16, 14, 16, 14)
        row.setSpacing(14)

        lbl_icon = QLabel()
        lbl_icon.setPixmap(icons.get_icon(icon_svg, icon_color, 28).pixmap(28, 28))
        lbl_icon.setFixedSize(28, 28)
        row.addWidget(lbl_icon)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        lbl_t = QLabel(title, objectName="card_title")
        lbl_s = QLabel(subtitle, objectName="card_sub")
        text_col.addWidget(lbl_t)
        text_col.addWidget(lbl_s)
        row.addLayout(text_col)
        row.addStretch()

        btn = QPushButton(btn_text, objectName=btn_color.lstrip("#"))
        btn.setFixedWidth(200)
        btn.clicked.connect(on_click)
        row.addWidget(btn)
        return card

    def _open(self, url: str, btn: QPushButton):
        QDesktopServices.openUrl(QUrl(url))
        btn.setEnabled(False)
        btn.setText(" Página Aberta ✓")
        self.lbl_status.setVisible(True)
        self.lbl_status.setText("Após instalar e abrir o software, reinicie o FuriousCam Pro.")


# ─────────────────────────────────────────────────────────────────
#  2. Dialog de instalação do Unity Capture
# ─────────────────────────────────────────────────────────────────
class UnityCaptureInstallDialog(QDialog):
    """
    Instala (ou desinstala) o driver Unity Capture bundled no app.
    Usa regsvr32 com ShellExecuteW 'runas' para elevação UAC nativa.
    Não depende de .bat externo.
    """

    def __init__(self, parent=None, base_path: str = None):
        super().__init__(parent)
        self.setWindowTitle("Gerenciar Driver — Unity Capture")
        self.setFixedSize(500, 430)
        self.setModal(True)

        # Localiza as DLLs bundled no projeto
        if base_path is None:
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        install_dir = os.path.join(base_path, "portables", "unity")
        self.dll32 = os.path.join(install_dir, "UnityCaptureFilter32.dll")
        self.dll64 = os.path.join(install_dir, "UnityCaptureFilter64.dll")
        self._dlls_found = os.path.exists(self.dll32) and os.path.exists(self.dll64)
        # Verifica se o driver já está instalado no sistema
        self._driver_installed = is_unity_capture_installed()
        self._worker = None

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
            QLabel#title  { color: #ffd54f; font-size: 16px; font-weight: 800; }
            QLabel#subtitle { color: #888; font-size: 11px; }
            QLabel#step   { color: #aaa; font-size: 11px; }
            QPushButton#install_btn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #f9a825, stop:1 #ffd54f);
                color: #000;
                border: none; border-radius: 8px;
                padding: 12px 24px;
                font-size: 13px; font-weight: 700;
            }
            QPushButton#install_btn:hover  { background: #ffd54f; }
            QPushButton#install_btn:disabled { background: #3a3010; color: #6b5b20; }
            QPushButton#uninstall_btn {
                background-color: #1a1a22;
                color: #ef9a9a;
                border: 1px solid #3a2222;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 11px;
            }
            QPushButton#uninstall_btn:hover { background-color: #2a1a1a; }
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
                    stop:0 #f9a825, stop:1 #ffd54f);
                border-radius: 4px;
            }
            QFrame#divider { background: #1e1e26; max-height: 1px; border: none; }
            QFrame#info_box {
                background-color: #111116;
                border: 1px solid #2a2a1a;
                border-radius: 8px;
            }
        """)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 24)
        layout.setSpacing(14)

        # Header — muda título e icone conforme estado do driver
        lbl_icon = QLabel()
        lbl_icon.setPixmap(icons.get_icon(icons.SVG_CAST, "#ffd54f", 32).pixmap(32, 32))
        lbl_title = QLabel("Unity Capture — Driver de Câmera Virtual", objectName="title")
        self.lbl_subtitle = QLabel("", objectName="subtitle")
        self.lbl_subtitle.setWordWrap(True)
        layout.addWidget(lbl_icon)
        layout.addWidget(lbl_title)
        layout.addWidget(self.lbl_subtitle)

        div = QFrame(objectName="divider")
        div.setFrameShape(QFrame.HLine)
        layout.addWidget(div)

        # Info box — muda conforme estado
        self.info_box = QFrame(objectName="info_box")
        self.info_layout = QVBoxLayout(self.info_box)
        self.info_layout.setContentsMargins(16, 12, 16, 12)
        self.info_layout.setSpacing(6)
        
        self._update_state_ui()

        layout.addWidget(self.info_box)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)   # indeterminate
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #ffd54f; font-size: 10px;")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setVisible(False)
        layout.addWidget(self.lbl_status)

        layout.addStretch()

        # Buttons — estado inicial reflete se já está instalado
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_install = QPushButton(" Instalar Driver", objectName="install_btn")
        self.btn_install.setIcon(icons.get_icon(icons.SVG_DOWNLOAD, "#000"))
        # Instalar só ativo se DLLs existem E driver NÃO está instalado
        self.btn_install.setEnabled(self._dlls_found and not self._driver_installed)
        self.btn_install.clicked.connect(self._do_install)
        btn_row.addWidget(self.btn_install)

        self.btn_uninstall = QPushButton("Remover Driver", objectName="uninstall_btn")
        # Remover só ativo se driver ESTÁ instalado
        self.btn_uninstall.setEnabled(self._driver_installed and self._dlls_found)
        self.btn_uninstall.clicked.connect(self._do_uninstall)
        btn_row.addWidget(self.btn_uninstall)

        btn_close = QPushButton("Fechar", objectName="close_btn")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)

        layout.addLayout(btn_row)

        lbl_credits = QLabel('<a href="https://github.com/schellingb/UnityCapture" style="color: #666; text-decoration: none;">Unity Capture Filter © Hendrik Scheiber — MIT License</a>')
        lbl_credits.setOpenExternalLinks(True)
        lbl_credits.setAlignment(Qt.AlignCenter)
        lbl_credits.setStyleSheet("font-size: 9px; margin-top: 5px;")
        layout.addWidget(lbl_credits)

    def _update_state_ui(self):
        # Update text
        if self._driver_installed:
            self.lbl_subtitle.setText(
                "Driver já está instalado no sistema.\n"
                "Para remover o driver, clique em Remover Driver."
            )
            items = [
                (icons.SVG_CHECK, "Driver registrado: Unity Video Capture"),
                (icons.SVG_CHECK, "Compatível com Discord, Zoom, Meet, TikTok Live Studio"),
                (icons.SVG_CHECK, "Para remover, clique em Remover Driver (requer permissão de Administrador)"),
            ]
            sym_color = "#00e676"
        elif self._dlls_found:
            self.lbl_subtitle.setText(
                "Driver leve (DirectShow) que permite usar o FuriousCam Pro como webcam\n"
                "sem precisar ter o OBS Studio instalado."
            )
            items = [
                (icons.SVG_STAR, "Driver bundled encontrado e pronto para instalar"),
                (icons.SVG_STAR, "Requer aprovação de Administrador (permissão de Administrador)"),
                (icons.SVG_STAR, "Aparecerá como \"Unity Video Capture\" no sistema"),
                (icons.SVG_STAR, "Compatível com Discord, Zoom, Meet, TikTok Live Studio"),
            ]
            sym_color = "#ffd54f"
        else:
            self.lbl_subtitle.setText("Arquivos do driver não encontrados localmente.")
            items = [
                (icons.SVG_ALERT, "DLLs do driver não encontradas no pacote do app"),
                (icons.SVG_ALERT, "A pasta portables/unity/ está ausente"),
                (icons.SVG_ALERT, "Baixe manualmente em github.com/schellingb/UnityCapture"),
            ]
            sym_color = "#ff8a65"

        # Clear layout
        while self.info_layout.count():
            item = self.info_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget(): sub.widget().deleteLater()
                item.layout().deleteLater()

        # Rebuild layout
        for svg_str, text in items:
            row = QHBoxLayout()
            row.setSpacing(10)
            sym_lbl = QLabel()
            sym_lbl.setPixmap(icons.get_icon(svg_str, sym_color, 16).pixmap(16, 16))
            sym_lbl.setFixedSize(16, 16)
            txt_lbl = QLabel(text, objectName="step")
            row.addWidget(sym_lbl)
            row.addWidget(txt_lbl)
            self.info_layout.addLayout(row)

    def _set_busy(self, busy: bool, action: str = ""):
        self.btn_install.setEnabled(not busy)
        self.btn_uninstall.setEnabled(not busy)
        self.progress_bar.setVisible(busy)
        if busy:
            self.lbl_status.setVisible(True)
            self.lbl_status.setText(f"{action}... Aprove o prompt de Administrador.")
            self.lbl_status.setStyleSheet("color: #ffd54f; font-size: 10px;")

    def _do_install(self):
        self._run_worker(unregister=False)

    def _do_uninstall(self):
        self._run_worker(unregister=True)

    def _run_worker(self, unregister: bool):
        action_name = "Remoção" if unregister else "Instalação"
        logger.info(f"Iniciando {action_name} do Unity Capture driver...")
        action = "Removendo driver" if unregister else "Instalando driver"
        self._set_busy(True, action)
        self._worker = RegSvr32Worker([self.dll32, self.dll64], unregister=unregister)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_finished(self, success: bool, message: str):
        self.progress_bar.setVisible(False)
        self.lbl_status.setVisible(True)
        
        # Atualiza o estado real do driver após a operação
        self._driver_installed = is_unity_capture_installed()
        
        if success:
            logger.info(f"Operação no Unity Capture concluída com sucesso: {message}. Estado atual: Instalado={self._driver_installed}")
            self.lbl_status.setStyleSheet("color: #00e676; font-size: 10px;")
            self.lbl_status.setText("✓ " + message)
            
            # Atualiza os textos da interface refletindo o novo estado!
            self._update_state_ui()
        else:
            logger.error(f"Falha na operação do Unity Capture: {message}")
            self.lbl_status.setStyleSheet("color: #ef9a9a; font-size: 10px;")
            self.lbl_status.setText(
                "✗ Falha na operação:\n" + message + "\n"
                "Tente executar o FuriousCam Pro como Administrador."
            )
            
        # Re-ajusta os botões com base no novo estado
        if self._dlls_found:
            self.btn_install.setEnabled(not self._driver_installed)
            self.btn_uninstall.setEnabled(self._driver_installed)
        
        # Restaura os textos originais caso tenham sido alterados
        self.btn_install.setText(" Instalar Driver")
        self.btn_uninstall.setText("Remover Driver")


# ─────────────────────────────────────────────────────────────────
#  3. Dialog VB-Cable (sem alterações)
# ─────────────────────────────────────────────────────────────────
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

        div = QFrame(objectName="divider")
        div.setFrameShape(QFrame.HLine)
        layout.addWidget(div)

        steps_frame = QFrame()
        steps_frame.setStyleSheet("background-color: #111116; border-radius: 8px; padding: 4px;")
        steps_layout = QVBoxLayout(steps_frame)
        steps_layout.setContentsMargins(16, 12, 16, 12)
        steps_layout.setSpacing(6)

        for num, text in [
            ("1.", "Baixe o VB-Cable for Windows no site oficial"),
            ("2.", "Extraia o arquivo .zip em uma pasta"),
            ("3.", "Execute 'VBCABLE_Setup_x64.exe' como Administrador"),
            ("4.", "Reinicie o PC (ou apenas o FuriousCam Pro) e tente novamente"),
        ]:
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
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl("https://vb-audio.com/Cable/"))
        self.lbl_progress.setVisible(True)
        self.lbl_progress.setText("Página aberta. Lembre-se de instalar como Administrador!")
        self.btn_download.setEnabled(False)
        self.btn_download.setText(" Página Aberta")
