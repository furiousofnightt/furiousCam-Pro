import threading
import sys
import os
import numpy as np
from PySide6.QtWidgets import (
    QMainWindow, QVBoxLayout, QHBoxLayout, QPushButton,
    QWidget, QLabel, QFrame, QComboBox, QSlider, QSizePolicy, QScrollArea,
    QMessageBox
)
import ui.icons as icons
from PySide6.QtGui import QImage, QPainter, QColor, QFont, QLinearGradient, QBrush, QPen, QFontDatabase, QIcon
from PySide6.QtCore import Qt, Slot, QTimer, QRect, QSize, QObject, QSettings
from PySide6.QtMultimedia import QMediaDevices
from ui.camera_window import CameraOnlyWindow
from transport.wifi_manager import WifiManager


# ─────────────────────────────────────────────
#  Video Preview Widget
# ─────────────────────────────────────────────
class VideoWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = None
        self.status_text = "Aguardando Câmera..."
        self.setMinimumSize(320, 240)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_image(self, img: QImage):
        self.image = img
        self.update()

    def set_status(self, text: str):
        self.image = None
        self.status_text = text
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()

        # Background
        painter.fillRect(rect, QColor(10, 10, 12))

        if self.image:
            scaled = self.image.scaled(rect.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = (rect.width() - scaled.width()) // 2
            y = (rect.height() - scaled.height()) // 2
            painter.drawImage(x, y, scaled)

            # Overlay: thin green border when live
            pen = QPen(QColor(0, 230, 118), 2)
            painter.setPen(pen)
            painter.drawRect(x, y, scaled.width() - 1, scaled.height() - 1)
        else:
            # No feed - draw placeholder
            grad = QLinearGradient(0, 0, 0, rect.height())
            grad.setColorAt(0, QColor(18, 18, 22))
            grad.setColorAt(1, QColor(10, 10, 14))
            painter.fillRect(rect, QBrush(grad))

            # Camera icon placeholder lines
            cx, cy = rect.width() // 2, rect.height() // 2
            painter.setPen(QPen(QColor(60, 60, 70), 2))
            painter.drawRoundedRect(cx - 40, cy - 28, 80, 56, 8, 8)
            painter.drawEllipse(cx - 16, cy - 16, 32, 32)

            # Status text
            painter.setPen(QColor(120, 120, 140))
            font = QFont("Segoe UI", 11)
            painter.setFont(font)
            painter.drawText(rect.adjusted(0, 60, 0, 0), Qt.AlignHCenter | Qt.AlignTop, self.status_text)


# ─────────────────────────────────────────────
#  Stat Badge
# ─────────────────────────────────────────────
class StatBadge(QWidget):
    def __init__(self, icon_svg: str, label: str, parent=None):
        super().__init__(parent)
        self._label = label
        self._value = "---"
        self.setFixedHeight(52)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(2)

        title_layout = QHBoxLayout()
        title_layout.setSpacing(4)
        title_layout.setContentsMargins(0, 0, 0, 0)

        self.lbl_icon = QLabel()
        self.lbl_icon.setPixmap(icons.get_icon(icon_svg, "#666", 12).pixmap(12, 12))

        self.lbl_title = QLabel(label)
        self.lbl_title.setStyleSheet("color: #666; font-size: 10px; font-weight: 600; letter-spacing: 1px;")
        self.lbl_title.setAlignment(Qt.AlignCenter)
        title_layout.addStretch()
        title_layout.addWidget(self.lbl_icon)
        title_layout.addWidget(self.lbl_title)
        title_layout.addStretch()

        self.lbl_value = QLabel("---")
        self.lbl_value.setStyleSheet("color: #e0e0e0; font-size: 14px; font-weight: 700;")
        self.lbl_value.setAlignment(Qt.AlignCenter)

        layout.addLayout(title_layout)
        layout.addWidget(self.lbl_value)
        layout.addStretch()

    def set_value(self, v: str):
        self._value = v
        self.lbl_value.setText(v)

    def set_active(self, active: bool):
        color = "#00e676" if active else "#e0e0e0"
        self.lbl_value.setStyleSheet(f"color: {color}; font-size: 14px; font-weight: 700;")

    def set_icon(self, icon_svg: str, color: str = "#666"):
        self.lbl_icon.setPixmap(icons.get_icon(icon_svg, color, 12).pixmap(12, 12))


# ─────────────────────────────────────────────
#  Wheel Blocker — evita que scroll mude valores
#  de QComboBox e QSlider dentro do sidebar
# ─────────────────────────────────────────────
class WheelBlocker(QObject):
    """Event filter that ignores wheel events on a widget,
    letting them propagate to the parent scroll area instead."""
    def eventFilter(self, obj, event):
        if event.type() == event.Type.Wheel:
            event.ignore()
            return True
        return super().eventFilter(obj, event)

# ─────────────────────────────────────────────
#  Help Icon — mostra tooltip ao clicar
# ─────────────────────────────────────────────
class HelpIcon(QLabel):
    """Um ícone de '?' que exibe o tooltip imediatamente ao ser clicado."""
    def __init__(self, tooltip_text, parent=None):
        super().__init__("?", parent)
        self.setFixedSize(14, 14)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("color: #aaa; background: #2a2d38; border-radius: 7px; font-size: 9px; font-weight: bold;")
        self.setToolTip(tooltip_text)
        self.setCursor(Qt.PointingHandCursor)
        self._tooltip_text = tooltip_text

    def mouseReleaseEvent(self, event):
        from PySide6.QtWidgets import QToolTip
        from PySide6.QtGui import QCursor
        QToolTip.showText(QCursor.pos(), self._tooltip_text, self)
        event.accept()


# ─────────────────────────────────────────────
#  FPS Sparkline — mini histograma de FPS
# ─────────────────────────────────────────────
class FpsSparkline(QWidget):
    """Draws a live sparkline chart of the last N FPS readings."""
    BAR_COUNT = 30  # seconds of history
    TARGET_FPS = 60

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history = [0.0] * self.BAR_COUNT
        self.setFixedSize(120, 46)
        self.setToolTip("Desempenho de FPS (últimos 30s)")

    def push(self, fps: float):
        self._history.pop(0)
        self._history.append(min(fps, self.TARGET_FPS))
        self.update()

    def reset(self):
        self._history = [0.0] * self.BAR_COUNT
        self.update()

    def paintEvent(self, event):
        from PySide6.QtGui import QPainterPath
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Background com gradiente super suave
        bg_grad = QLinearGradient(0, 0, 0, h)
        bg_grad.setColorAt(0, QColor(20, 20, 26))
        bg_grad.setColorAt(1, QColor(12, 12, 16))
        p.fillRect(self.rect(), bg_grad)

        # Subtle Grid Lines
        p.setPen(QPen(QColor(40, 40, 50, 80), 1, Qt.DashLine))
        for i in range(1, 4):
            y = i * h / 4
            p.drawLine(0, int(y), w, int(y))

        # Determinar a cor baseada no FPS mais recente
        current_fps = self._history[-1]
        if current_fps >= 50:
            base_color = QColor(0, 230, 118) # Neon Green
        elif current_fps >= 25:
            base_color = QColor(255, 193, 7) # Amber
        else:
            base_color = QColor(255, 82, 82) # Red

        # Gerar os pontos da curva
        points = []
        margin_x = 2
        margin_y = 4
        usable_w = w - (margin_x * 2)
        usable_h = h - (margin_y * 2)
        
        step_x = usable_w / max(1, (self.BAR_COUNT - 1))

        for i, fps in enumerate(self._history):
            ratio = fps / self.TARGET_FPS if self.TARGET_FPS else 0
            x = margin_x + i * step_x
            y = h - margin_y - (ratio * usable_h)
            points.append((x, y))

        if not points:
            return

        # Criar QPainterPath para linha e preenchimento
        path = QPainterPath()
        path.moveTo(points[0][0], points[0][1])

        # Curva suave (bezier)
        for i in range(1, len(points)):
            p0 = points[i-1]
            p1 = points[i]
            ctrl1_x = (p0[0] + p1[0]) / 2.0
            ctrl1_y = p0[1]
            ctrl2_x = (p0[0] + p1[0]) / 2.0
            ctrl2_y = p1[1]
            path.cubicTo(ctrl1_x, ctrl1_y, ctrl2_x, ctrl2_y, p1[0], p1[1])

        # --- Desenhar preenchimento (Glow abaixo da linha) ---
        fill_path = QPainterPath(path)
        fill_path.lineTo(points[-1][0], h)
        fill_path.lineTo(points[0][0], h)
        fill_path.closeSubpath()

        fill_grad = QLinearGradient(0, 0, 0, h)
        glow_color = QColor(base_color)
        glow_color.setAlpha(60) # topo translúcido
        fade_color = QColor(base_color)
        fade_color.setAlpha(0)  # base transparente

        fill_grad.setColorAt(0, glow_color)
        fill_grad.setColorAt(1, fade_color)
        p.setBrush(fill_grad)
        p.setPen(Qt.NoPen)
        p.drawPath(fill_path)

        # --- Desenhar a Linha Principal ---
        pen = QPen(base_color, 2.0)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)

        # --- Ponto brilhante no último valor ---
        last_x, last_y = points[-1]
        
        # Glow do ponto
        glow_dot_color = QColor(base_color)
        glow_dot_color.setAlpha(120)
        p.setPen(Qt.NoPen)
        p.setBrush(glow_dot_color)
        p.drawEllipse(int(last_x - 4), int(last_y - 4), 8, 8)

        # Ponto central sólido
        p.setBrush(QColor(255, 255, 255))
        p.drawEllipse(int(last_x - 2), int(last_y - 2), 4, 4)

        # --- Borda do Widget ---
        border_grad = QLinearGradient(0, 0, w, h)
        border_grad.setColorAt(0, QColor(50, 54, 66))
        border_grad.setColorAt(1, QColor(28, 30, 38))
        p.setPen(QPen(border_grad, 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(0, 0, w - 1, h - 1, 6, 6)



# ─────────────────────────────────────────────
class AudioVolumeMeter(QWidget):
    """
    VU Meter no estilo TikTok Live Studio.
    Uma barra preenchida da esquerda para a direita (ou de baixo pra cima),
    com gradiente mudando de verde -> amarelo -> vermelho conforme o volume sobe.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(10, 8)
        self.setFixedHeight(8)
        self._level = 0 # 0 a 100

    def set_level(self, level: int):
        # Suavização simples para não piscar muito rápido (decay)
        if level > self._level:
            self._level = level
        else:
            self._level = max(0, self._level - 5) # decaimento suave
        self.update()

    def paintEvent(self, event):
        from PySide6.QtGui import QPainter, QPainterPath, QColor, QLinearGradient
        from PySide6.QtCore import Qt
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        # Background dark
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(30, 32, 40))
        p.drawRoundedRect(0, 0, w, h, h//2, h//2)
        
        if self._level > 0:
            fill_w = int((self._level / 100.0) * w)
            if fill_w > 0:
                # Gradiente para o preenchimento (verde -> amarelo -> vermelho)
                grad = QLinearGradient(0, 0, w, 0)
                grad.setColorAt(0.0, QColor(0, 230, 118))   # Verde neon
                grad.setColorAt(0.7, QColor(255, 193, 7))   # Amarelo
                grad.setColorAt(1.0, QColor(255, 82, 82))   # Vermelho
                
                p.setBrush(grad)
                p.drawRoundedRect(0, 0, fill_w, h, h//2, h//2)

# ─────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self, core_manager, log_file_path: str = ""):
        super().__init__()
        self.core = core_manager
        self.is_drawing = False
        self.is_connected = False
        self._rotation = 0  # degrees: 0, 90, 180, 270
        self._camera_window: CameraOnlyWindow | None = None
        self._log_file_path = log_file_path    # Caminho para furiouscam.log
        self._log_viewer_dialog = None         # Instância única (não-modal)

        self.setWindowTitle("FuriousCam Pro")
        self.resize(1060, 680)
        self.setMinimumSize(800, 520)
        self._apply_global_style()
        self._build_ui()
        self._start_render_timer()

        # Connect signals once (not on every start)
        self.core.connection_status.connect(self.update_status)
        self.core.stats_updated.connect(self.update_stats)
        self.core.camera_swapped.connect(self.on_camera_swapped)
        self.core.stream_info_ui.connect(self._on_stream_info_auto_rotate)
        self.core.stream_info_ui.connect(self._on_stream_info_sync_wifi_flag)
        self.core.show_warning.connect(self.show_warning_dialog)
        self.core.audio_level.connect(self._on_audio_level)  # VU Meter

        # Setup config.ini path — sempre ao lado do .exe (ou do script em dev)
        if getattr(sys, 'frozen', False):
            # Executável PyInstaller: config fica ao lado do FuriousCam.exe
            config_dir = os.path.dirname(sys.executable)
        else:
            # Desenvolvimento: config fica na raiz do projeto
            config_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(config_dir, "config.ini")
        self.settings = QSettings(config_path, QSettings.IniFormat)
        self._load_settings()

        # Ícone da janela e da taskbar
        icon_path = None
        if getattr(sys, 'frozen', False):
            icon_path = os.path.join(os.path.dirname(sys.executable), 'portables', 'images', 'furiouscam_safe.ico')
        else:
            icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'portables', 'images', 'furiouscam_safe.ico')
        if icon_path and os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Initialize Wi-Fi Manager
        self.wifi_manager = WifiManager(self.core, self)
        
        # Build the settings popup menu (gear icon)
        self._build_settings_menu()
        
        # Connect Wi-Fi submenu actions to WifiManager slots
        self._connect_wifi_menu_actions()

    def _build_settings_menu(self):
        """Creates the settings QMenu with OBS, Camera Window, and Wi-Fi controls."""
        from PySide6.QtWidgets import QMenu, QWidgetAction
        
        self._settings_menu = QMenu(self)
        self._settings_menu.setStyleSheet("""
            QMenu {
                background-color: #16181f;
                border: 1px solid #2a2d38;
                border-radius: 10px;
                padding: 6px;
            }
            QMenu::item {
                padding: 0px;
                background: transparent;
            }
            QMenu::item:has-children {
                padding: 8px 12px;
                color: #d0d0e0;
                font-size: 12px;
                border-radius: 6px;
            }
            QMenu::item:has-children:selected {
                background: #1e2028;
            }
            QMenu::separator {
                height: 1px;
                background: #2a2d38;
                margin: 4px 8px;
            }
            QMenu::right-arrow {
                right: 12px;
            }
        """)
        
        def _make_action_widget(icon_svg, color, label, checkable=False):
            btn = QPushButton(f"  {label}")
            btn.setIcon(icons.get_icon(icon_svg, color, 16))
            btn.setCheckable(checkable)
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    border-radius: 6px;
                    color: #d0d0e0;
                    font-size: 12px;
                    text-align: left;
                    padding: 8px 12px;
                    min-width: 210px;
                }
                QPushButton:hover { background: #1e2028; }
                QPushButton:checked { background: #0d2b1e; color: #00e676; }
                QPushButton::menu-indicator { image: none; }
            """)
            action = QWidgetAction(self._settings_menu)
            action.setDefaultWidget(btn)
            return action, btn
        
        # Title label
        title_lbl = QLabel("  Saídas & Conexão")
        title_lbl.setStyleSheet("color: #555; font-size: 10px; font-weight: 600; padding: 4px 12px; letter-spacing: 1px;")
        title_action = QWidgetAction(self._settings_menu)
        title_action.setDefaultWidget(title_lbl)
        self._settings_menu.addAction(title_action)
        self._settings_menu.addSeparator()
        
        # OBS Virtual Camera
        obs_action, self.btn_obs = _make_action_widget(icons.SVG_CAST, "#c0c0d0", "Ativar Câmera Virtual (OBS)", checkable=True)
        self.btn_obs.clicked.connect(self._toggle_obs)
        self.btn_obs.setEnabled(False)
        self._settings_menu.addAction(obs_action)
        
        self.lbl_obs_status = QLabel("  OBS Virtual Camera: inativo")
        self.lbl_obs_status.setStyleSheet("color: #444; font-size: 9px; padding: 0 12px 4px 12px;")
        obs_status_action = QWidgetAction(self._settings_menu)
        obs_status_action.setDefaultWidget(self.lbl_obs_status)
        self._settings_menu.addAction(obs_status_action)
        self._settings_menu.addSeparator()

        # Unity Capture (Experimental)
        unity_action, self.btn_unity = _make_action_widget(icons.SVG_CAST, "#ffd54f", "Câmera Virtual (Streamlabs / Web)", checkable=True)
        self.btn_unity.clicked.connect(self._toggle_unity)
        self.btn_unity.setEnabled(False)
        self._settings_menu.addAction(unity_action)

        self.lbl_unity_status = QLabel("  Câmera Universal: inativo")
        self.lbl_unity_status.setStyleSheet("color: #444; font-size: 9px; padding: 0 12px 2px 12px;")
        unity_status_action = QWidgetAction(self._settings_menu)
        unity_status_action.setDefaultWidget(self.lbl_unity_status)
        self._settings_menu.addAction(unity_status_action)

        # Botão "Gerenciar driver..." — sempre visível, abre install/uninstall dialog
        # Solução definitiva: right-click não funciona dentro de QMenu no Qt
        self.btn_unity_manage = QPushButton(" Gerenciar driver Universal...")
        self.btn_unity_manage.setIcon(icons.get_icon(icons.SVG_GEAR, "#888", 16))
        self.btn_unity_manage.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #555;
                font-size: 9px;
                text-align: left;
                padding: 2px 12px 6px 12px;
                min-width: 210px;
            }
            QPushButton:hover { color: #ffd54f; background: transparent; }
        """)
        self.btn_unity_manage.setCursor(Qt.PointingHandCursor)
        self.btn_unity_manage.clicked.connect(self._show_unity_install_dialog)
        unity_manage_action = QWidgetAction(self._settings_menu)
        unity_manage_action.setDefaultWidget(self.btn_unity_manage)
        self._settings_menu.addAction(unity_manage_action)
        self._settings_menu.addSeparator()

        

        # Camera Window
        cam_win_action, self.btn_camera_window = _make_action_widget(icons.SVG_WINDOW, "#90caf9", "Janela Flutuante de Câmera", checkable=True)
        self.btn_camera_window.clicked.connect(self._toggle_camera_window)
        self.btn_camera_window.setEnabled(False)
        self._settings_menu.addAction(cam_win_action)
        self._settings_menu.addSeparator()
        
        # Wi-Fi Options — submenu nativo
        menu_style = """
            QMenu {
                background-color: #16181f;
                border: 1px solid #2a2d38;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                color: #d0d0e0;
                font-size: 12px;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QMenu::item:selected { background: #1e2028; }
            QMenu::item:disabled { color: #444; }
            QMenu::separator { height: 1px; background: #2a2d38; margin: 3px 6px; }
        """
        self.wifi_submenu = QMenu(self._settings_menu)
        self.wifi_submenu.setStyleSheet(menu_style)

        self.act_wifi_hybrid = self.wifi_submenu.addAction(
            icons.get_icon(icons.SVG_WIFI, "#00e676", 16), "Ativar Wi-Fi (Modo Híbrido Automático)"
        )
        self.act_wifi_ip = self.wifi_submenu.addAction(
            icons.get_icon(icons.SVG_SMARTPHONE, "#ffeb3b", 16), "Conectar por Endereço IP Manual"
        )
        self.wifi_submenu.addSeparator()
        self.act_wifi_usb = self.wifi_submenu.addAction(
            icons.get_icon(icons.SVG_CAST, "#90caf9", 16), "Voltar para Cabo USB"
        )
        self.act_wifi_usb.setEnabled(False)  # Só ativo quando em modo Wi-Fi

        # Cria a ação do submenu exatamente igual aos outros botões
        wifi_action, self.btn_wifi = _make_action_widget(icons.SVG_WIFI, "#ffeb3b", "Conexão Wi-Fi")
        # Define o menu manualmente para evitar que o Qt sobrescreva o CSS do botão e o converta em um QMenu::item nativo.
        def show_wifi_menu():
            from PySide6.QtCore import QPoint
            # Mostra o submenu ao lado direito do botão
            pos = self.btn_wifi.mapToGlobal(QPoint(self.btn_wifi.width(), 0))
            self.wifi_submenu.popup(pos)
            
        self.btn_wifi.clicked.connect(show_wifi_menu)
        
        # Opcional: Adicionar a setinha svg pro lado direito do botão pra ficar igual ao menu original
        arrow_lbl = QLabel(self.btn_wifi)
        arrow_lbl.setPixmap(icons.get_icon('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>', "#888", 14).pixmap(14, 14))
        arrow_lbl.setStyleSheet("background: transparent;")
        arrow_lbl.move(200, 10)  # Posicionado manualmente no canto direito

        self._settings_menu.addAction(wifi_action)
        self._settings_menu.addSeparator()

        # Log Viewer
        log_action, self.btn_log_viewer = _make_action_widget(
            icons.SVG_FILE_TEXT, "#80cbc4", "Ver Logs do Sistema"
        )
        self.btn_log_viewer.clicked.connect(self._open_log_viewer)
        self._settings_menu.addAction(log_action)

        # Signals conectados depois que wifi_manager for criado
        # (feito em _connect_wifi_menu_actions, chamado após _build_settings_menu)

    def _connect_wifi_menu_actions(self):
        """Conecta os itens do submenu Wi-Fi ao WifiManager."""
        self.act_wifi_hybrid.triggered.connect(self.wifi_manager.action_hybrid_mode)
        self.act_wifi_ip.triggered.connect(self.wifi_manager.action_connect_ip_manual)
        self.act_wifi_usb.triggered.connect(self.wifi_manager.action_return_to_usb)

    def _open_settings_menu(self):
        """Pops the settings menu below the gear button, right-aligned."""
        menu = self._settings_menu
        menu.adjustSize()
        from PySide6.QtCore import QPoint
        btn_rect = self.btn_settings.rect()
        bottom_right = self.btn_settings.mapToGlobal(btn_rect.bottomRight())
        menu_size = menu.sizeHint()
        pos = QPoint(bottom_right.x() - menu_size.width(), bottom_right.y() + 4)
        menu.exec(pos)


    def _apply_global_style(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #0d0d10;
                color: #e0e0e0;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QFrame#sidebar {
                background-color: #111116;
                border-right: 1px solid #222228;
            }
            QFrame#topbar {
                background-color: #111116;
                border-bottom: 1px solid #222228;
            }
            QFrame#statsBar {
                background-color: #0f0f13;
                border-top: 1px solid #1a1a22;
            }
            QPushButton#btnStart {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00c853, stop:1 #00e676);
                color: #000;
                border: none;
                border-radius: 8px;
                padding: 10px 22px;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton#btnStart:hover { background: #00e676; }
            QPushButton#btnStart:disabled { background: #1a3d2a; color: #2d6b45; }

            QPushButton#btnStop {
                background-color: #1a1a20;
                color: #ff5252;
                border: 1px solid #ff5252;
                border-radius: 8px;
                padding: 10px 22px;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton#btnStop:hover { background-color: #2a1010; }
            QPushButton#btnStop:disabled { border-color: #333; color: #555; }

            QPushButton#btnCamFlip {
                background-color: #1a1a22;
                color: #90caf9;
                border: 1px solid #2a3a4a;
                border-radius: 8px;
                padding: 10px 16px;
                font-size: 12px;
                min-height: 20px;
            }
            QPushButton#btnCamFlip:hover { background-color: #1e2535; }

            QComboBox {
                background-color: #1a1a22;
                color: #c0c0d0;
                border: 1px solid #2a2a35;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12px;
                min-height: 24px;
            }
            QComboBox::drop-down { border: none; width: 20px; }
            QComboBox QAbstractItemView {
                background-color: #1a1a22;
                color: #c0c0d0;
                selection-background-color: #00c853;
                selection-color: #000;
                border: 1px solid #333;
            }

            QSlider::groove:horizontal {
                height: 4px;
                background: #2a2a35;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #00e676;
                width: 14px; height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QSlider::sub-page:horizontal {
                background: #00c853;
                border-radius: 2px;
            }

            QLabel#sectionLabel {
                color: #00e676;
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 2px;
            }
            QLabel#statusLabel {
                color: #666;
                font-size: 11px;
            }
            QLabel#recIndicator {
                color: #ff5252;
                font-size: 11px;
                font-weight: 700;
            }
            QFrame.separator {
                background: #1e1e26;
                max-height: 1px;
            }
            QWidget#sidebarContent {
                background-color: transparent;
            }
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #2a2a35;
                min-height: 30px;
                border-radius: 4px;
                margin: 0px 2px 0px 0px;
            }
            QScrollBar::handle:vertical:hover {
                background: #00c853;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Top bar ──
        topbar = QFrame(objectName="topbar")
        topbar.setFixedHeight(52)
        tb_layout = QHBoxLayout(topbar)
        tb_layout.setContentsMargins(16, 0, 16, 0)

        logo_layout = QHBoxLayout()
        logo_layout.setSpacing(6)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        lbl_logo_icon = QLabel()
        lbl_logo_icon.setPixmap(icons.get_icon(icons.SVG_VIDEO, "#00e676", 20).pixmap(20, 20))
        lbl_logo = QLabel("FuriousCam Pro")
        lbl_logo.setStyleSheet("font-size: 16px; font-weight: 800; color: #00e676; letter-spacing: 1px;")
        logo_layout.addWidget(lbl_logo_icon)
        logo_layout.addWidget(lbl_logo)
        tb_layout.addLayout(logo_layout)
        tb_layout.addStretch()

        self.lbl_status = QLabel("Aguardando...", objectName="statusLabel")
        tb_layout.addWidget(self.lbl_status)

        self.lbl_rec = QLabel("● AO VIVO", objectName="recIndicator")
        self.lbl_rec.setStyleSheet("padding: 0 4px;")
        self.lbl_rec.setVisible(False)
        tb_layout.addWidget(self.lbl_rec)

        root_layout.addWidget(topbar)

        # ── Content row ──
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # ── Sidebar ──
        sidebar = QFrame(objectName="sidebar")
        sidebar.setFixedWidth(270)
        sidebar.setFrameShape(QFrame.StyledPanel)
        sb_main_layout = QVBoxLayout(sidebar)
        sb_main_layout.setContentsMargins(0, 0, 1, 0)
        sb_main_layout.setSpacing(0)

        # ── Sidebar Header (gear button) ──
        sb_header = QFrame()
        sb_header.setStyleSheet("background: #111318; border-bottom: 1px solid #1e2028;")
        sb_header.setFixedHeight(40)
        sb_header_layout = QHBoxLayout(sb_header)
        sb_header_layout.setContentsMargins(12, 0, 8, 0)
        sb_header_layout.setSpacing(0)

        sb_header_title = QLabel("Configurações")
        sb_header_title.setStyleSheet("color: #00e676; font-size: 10px; font-weight: 600; letter-spacing: 1px;")
        sb_header_layout.addWidget(sb_header_title)
        sb_header_layout.addStretch()

        self.btn_settings = QPushButton()
        self.btn_settings.setIcon(icons.get_icon(icons.SVG_GEAR, "#888", 18))
        self.btn_settings.setFixedSize(30, 30)
        self.btn_settings.setToolTip("Saídas & Conexão Sem Fio")
        self.btn_settings.setStyleSheet("""
            QPushButton {
                background: transparent; border: none; border-radius: 6px;
            }
            QPushButton:hover { background: #1e2028; }
            QPushButton:pressed { background: #2a2d38; }
        """)
        self.btn_settings.clicked.connect(self._open_settings_menu)
        sb_header_layout.addWidget(self.btn_settings)

        sb_main_layout.addWidget(sb_header)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        scroll_content = QWidget()
        scroll_content.setObjectName("sidebarContent")
        sb_layout = QVBoxLayout(scroll_content)
        sb_layout.setContentsMargins(20, 24, 20, 24)
        sb_layout.setSpacing(14)

        # Section: Camera
        self._add_section_label(sb_layout, "CÂMERA", 
            "Escolha entre a câmera frontal ou traseira do aparelho. Você pode alternar em tempo real.")

        self.combo_camera = QComboBox()
        self.combo_camera.addItem(icons.get_icon(icons.SVG_CAMERA, "#c0c0d0"), " Traseira (Principal)", 0)
        self.combo_camera.addItem(icons.get_icon(icons.SVG_SMARTPHONE, "#c0c0d0"), " Frontal", 1)
        self.combo_camera.currentIndexChanged.connect(self._on_camera_changed)
        sb_layout.addWidget(self.combo_camera)

        self.btn_flip = QPushButton(" Alternar Câmera", objectName="btnCamFlip")
        self.btn_flip.setIcon(icons.get_icon(icons.SVG_FLIP, "#90caf9"))
        self.btn_flip.clicked.connect(self._flip_camera)
        sb_layout.addWidget(self.btn_flip)

        sb_layout.addWidget(self._separator())

        # Section: Rotation
        self._add_section_label(sb_layout, "ROTAÇÃO", 
            "Ajusta a orientação da imagem para não ficar de ponta cabeça ou deitada.\n"
            "Dica: O botão 'Auto' lê o sensor do aparelho (se disponível).")

        rot_layout = QHBoxLayout()
        rot_layout.setSpacing(6)
        self._rot_buttons = []
        for label, deg in [("0°", 0), ("90°", 90), ("180°", 180), ("270°", 270)]:
            btn = QPushButton(label, objectName="btnCamFlip")
            btn.setFixedHeight(34)
            btn.clicked.connect(lambda _, d=deg: self._set_rotation(d))
            self._rot_buttons.append((btn, deg))
            rot_layout.addWidget(btn)
        sb_layout.addLayout(rot_layout)

        self.btn_auto_rotate = QPushButton(" Auto", objectName="btnCamFlip")
        self.btn_auto_rotate.setIcon(icons.get_icon(icons.SVG_ROTATE, "#c0c0d0"))
        self.btn_auto_rotate.clicked.connect(self._auto_rotate)
        sb_layout.addWidget(self.btn_auto_rotate)

        self.btn_mirror = QPushButton(" Desespelhar Imagem", objectName="btnCamFlip")
        self.btn_mirror.setIcon(icons.get_icon(icons.SVG_FLIP, "#a5d6a7"))
        self.btn_mirror.setCheckable(True)
        self.btn_mirror.setChecked(True)
        self.btn_mirror.clicked.connect(self._toggle_mirror)
        sb_layout.addWidget(self.btn_mirror)

        sb_layout.addWidget(self._separator())

        # Section: Quality
        self._add_section_label(sb_layout, "QUALIDADE", 
            "Ajuste a resolução e os quadros por segundo.\n"
            "Valores mais altos exigem mais processamento e uma rede Wi-Fi / cabo USB mais rápido.\n\n"
            "Nota: Em alguns aparelhos, o sistema Android pode limitar a captura da câmera a 30 FPS via hardware.")

        self.combo_res = QComboBox()
        self.combo_res.addItem(icons.get_icon(icons.SVG_MONITOR, "#ab47bc"), " 2K Quad HD  2560×1440", (2560, 1440))
        self.combo_res.addItem(icons.get_icon(icons.SVG_LAYERS, "#ff9800"), " Full HD  1920×1080", (1920, 1080))
        self.combo_res.addItem(icons.get_icon(icons.SVG_ZAP, "#00bcd4"), " HD  1280×720", (1280, 720))
        self.combo_res.addItem(icons.get_icon(icons.SVG_BOX, "#8bc34a"), " 480p  854×480", (854, 480))
        self.combo_res.setCurrentIndex(1)  # Default to Full HD
        sb_layout.addWidget(self.combo_res)

        self.combo_fps = QComboBox()
        self.combo_fps.addItem("60 FPS", 60)
        self.combo_fps.addItem("30 FPS", 30)
        self.combo_fps.addItem("24 FPS", 24)
        self.combo_fps.setCurrentIndex(1)
        sb_layout.addWidget(self.combo_fps)

        lbl_bitrate = QLabel("Bitrate")
        lbl_bitrate.setStyleSheet("color: #00e676; font-size: 10px; font-weight: 600; letter-spacing: 1px;")
        
        btn_bitrate_help = HelpIcon(
            "Controla a qualidade da imagem da transmissão.\n"
            "2-4 Mbps: Rede lenta / 480p\n"
            "8 Mbps (Recomendado): Boa experiência. Usar cabo USB ou rede Wi-Fi 5GHz potente.\n"
            "12+ Mbps: Alta qualidade / 2K"
        )
        
        bitrate_header_layout = QHBoxLayout()
        bitrate_header_layout.setContentsMargins(0, 0, 0, 0)
        bitrate_header_layout.addWidget(lbl_bitrate)
        bitrate_header_layout.addWidget(btn_bitrate_help)
        bitrate_header_layout.addStretch()
        sb_layout.addLayout(bitrate_header_layout)

        self.slider_bitrate = QSlider(Qt.Horizontal)
        self.slider_bitrate.setRange(2, 20)
        self.slider_bitrate.setValue(8)
        self.slider_bitrate.setTickInterval(2)
        self.slider_bitrate.valueChanged.connect(self._on_bitrate_changed)
        sb_layout.addWidget(self.slider_bitrate)

        self.lbl_bitrate_val = QLabel("8 Mbps")
        self.lbl_bitrate_val.setStyleSheet("color: #00e676; font-size: 11px; font-weight: 600;")
        sb_layout.addWidget(self.lbl_bitrate_val)

        sb_layout.addWidget(self._separator())

        # Section: Áudio
        self._add_section_label(sb_layout, "ÁUDIO (BETA)", 
            "Captura o som do microfone do celular.\n"
            "Dica de Ouro: Para garantir a captura correta, ligue 'Ativar Microfone' ANTES de clicar em Iniciar Transmissão.\n\n"
            "Redução de Ruído: Remove ruído de fundo. Fique em silêncio por 1 seg ao ativar para o filtro aprender o ruído do ambiente.\n\n"
            "Me Ouvir: Toca o áudio no seu fone/caixa de som para você testar a qualidade.")
        
        self.btn_mic = QPushButton(" Ativar Microfone", objectName="btnCamFlip")
        self.btn_mic.setIcon(icons.get_icon(icons.SVG_MIC, "#ffc107"))
        self.btn_mic.setCheckable(True)
        self.btn_mic.clicked.connect(self._toggle_mic)
        sb_layout.addWidget(self.btn_mic)
        
        self.audio_meter = AudioVolumeMeter()
        self.audio_meter.setVisible(False)  # Só aparece quando mic estiver ligado
        sb_layout.addWidget(self.audio_meter)
        
        # Botão de Redução de Ruído — aparece junto com o mic
        self.btn_noise_reduction = QPushButton(" Redução de Ruído", objectName="btnCamFlip")
        self.btn_noise_reduction.setIcon(icons.get_icon(icons.SVG_MIC, "#a0a0b0"))
        self.btn_noise_reduction.setCheckable(True)
        self.btn_noise_reduction.setVisible(False)  # Só aparece quando mic ativo
        self.btn_noise_reduction.setToolTip(
            "Filtragem espectral de ruído de fundo (noisereduce).\n"
            "Captura o perfil de ruído nos primeiros 0.5s e remove-o em tempo real."
        )
        self.btn_noise_reduction.clicked.connect(self._toggle_noise_reduction)
        sb_layout.addWidget(self.btn_noise_reduction)
        
        # Botão de Monitor de Áudio (Ouvir Retorno)
        self.btn_monitor = QPushButton(" Ouvir Retorno", objectName="btnCamFlip")
        self.btn_monitor.setIcon(icons.get_icon(icons.SVG_VOLUME, "#a0a0b0"))
        self.btn_monitor.setCheckable(True)
        self.btn_monitor.setVisible(False)
        self.btn_monitor.setToolTip("Reproduz o áudio do celular nos alto-falantes do PC para monitoramento.")
        self.btn_monitor.clicked.connect(self._toggle_monitoring)
        sb_layout.addWidget(self.btn_monitor)
        
        # Seletor de Saída de Áudio
        self.combo_audio_out = QComboBox(objectName="comboAudioOut")
        self.combo_audio_out.setVisible(False)
        self.combo_audio_out.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.combo_audio_out.setToolTip("Escolha para onde enviar o áudio (ex: Alto-falantes ou Virtual Audio Cable para o OBS).")
        self._audio_devices = QMediaDevices.audioOutputs()
        for dev in self._audio_devices:
            self.combo_audio_out.addItem(dev.description())
        self.combo_audio_out.currentIndexChanged.connect(self._on_audio_out_changed)
        sb_layout.addWidget(self.combo_audio_out)
        
        # Botão de instalar VB-Cable
        self.btn_install_vbcable = QPushButton(" Faltando Cabo Virtual?", objectName="btnCamFlip")
        self.btn_install_vbcable.setIcon(icons.get_icon(icons.SVG_DOWNLOAD, "#ff9800"))
        self.btn_install_vbcable.setToolTip("Instale o VB-Cable para usar o áudio no OBS ou Discord")
        self.btn_install_vbcable.clicked.connect(self._show_vbcable_install_dialog)
        self.btn_install_vbcable.setVisible(False)
        sb_layout.addWidget(self.btn_install_vbcable)
        
        sb_layout.addWidget(self._separator())


        # Connection buttons
        self.btn_start = QPushButton(" Conectar Câmera", objectName="btnStart")
        self.btn_start.setIcon(icons.get_icon(icons.SVG_PLAY, "#000"))
        self.btn_start.clicked.connect(self.on_start_clicked)
        sb_layout.addWidget(self.btn_start)

        self.btn_stop = QPushButton(" Parar", objectName="btnStop")
        self.btn_stop.setIcon(icons.get_icon(icons.SVG_STOP, "#ff5252"))
        self.btn_stop.clicked.connect(self.on_stop_clicked)
        self.btn_stop.setEnabled(False)
        sb_layout.addWidget(self.btn_stop)

        sb_layout.addStretch()

        scroll.setWidget(scroll_content)
        sb_main_layout.addWidget(scroll)

        # ── Wheel Blocker ──
        # Impede que o scroll do mouse altere valores de ComboBox e Slider
        # enquanto o usuário apenas navega pelo sidebar.
        self._wheel_blocker = WheelBlocker(self)
        for widget in [
            self.combo_camera, self.combo_fps, self.combo_res,
            self.combo_audio_out, self.slider_bitrate,
        ]:
            widget.setFocusPolicy(Qt.StrongFocus)
            widget.installEventFilter(self._wheel_blocker)

        content_layout.addWidget(sidebar)

        # ── Video Preview ──
        self.video_widget = VideoWidget()
        content_layout.addWidget(self.video_widget, stretch=1)

        root_layout.addWidget(content, stretch=1)

        # ── Stats bar ──
        stats_bar = QFrame(objectName="statsBar")
        stats_bar.setFixedHeight(58)
        stats_layout = QHBoxLayout(stats_bar)
        stats_layout.setContentsMargins(16, 0, 16, 0)
        stats_layout.setSpacing(0)

        self.stat_fps = StatBadge(icons.SVG_ZAP, "FPS")
        self.stat_res = StatBadge(icons.SVG_MONITOR, "RESOLUÇÃO")
        self.stat_source = StatBadge(icons.SVG_CAMERA, "FONTE")
        self.stat_device = StatBadge(icons.SVG_SMARTPHONE, "DISPOSITIVO")
        self.stat_bitrate = StatBadge(icons.SVG_RADIO, "BITRATE")
        self.stat_latency = StatBadge(icons.SVG_ZAP, "LATÊNCIA")

        for s in [self.stat_fps, self.stat_res, self.stat_source, self.stat_device, self.stat_bitrate, self.stat_latency]:
            stats_layout.addWidget(s)
            stats_layout.addWidget(self._vseparator())

        # FPS sparkline
        self.fps_sparkline = FpsSparkline()
        sparkline_wrapper = QWidget()
        sparkline_layout = QVBoxLayout(sparkline_wrapper)
        sparkline_layout.setContentsMargins(16, 6, 0, 6)  # Top/bottom margins force perfect vertical centering
        sparkline_layout.addWidget(self.fps_sparkline)
        stats_layout.addWidget(sparkline_wrapper)

        root_layout.addWidget(stats_bar)

    def _add_section_label(self, layout, text, tooltip=None):
        lbl = QLabel(text, objectName="sectionLabel")
        if tooltip:
            h_layout = QHBoxLayout()
            h_layout.setContentsMargins(0, 0, 0, 0)
            h_layout.addWidget(lbl)
            
            help_icon = HelpIcon(tooltip)
            
            h_layout.addWidget(help_icon)
            h_layout.addStretch()
            layout.addLayout(h_layout)
        else:
            layout.addWidget(lbl)

    def _separator(self):
        f = QFrame()
        f.setFrameShape(QFrame.HLine)
        f.setStyleSheet("background: #1e1e26; max-height: 1px; border: none;")
        return f

    def _vseparator(self):
        f = QFrame()
        f.setFrameShape(QFrame.VLine)
        f.setStyleSheet("background: #1e1e26; max-width: 1px; border: none;")
        f.setFixedWidth(1)
        return f

    def _start_render_timer(self):
        self.render_timer = QTimer(self)
        self.render_timer.timeout.connect(self.pull_frame)
        self.render_timer.start(16)  # ~60 fps

    # ── Event handlers ──

    def _on_camera_changed(self, index):
        cam_id = self.combo_camera.itemData(index)
        self.core.set_camera(cam_id)

    def _flip_camera(self):
        cur = self.combo_camera.currentIndex()
        new_idx = 1 - cur
        new_cam_id = self.combo_camera.itemData(new_idx)
        # Block signals so _on_camera_changed doesn't double-fire
        self.combo_camera.blockSignals(True)
        self.combo_camera.setCurrentIndex(new_idx)
        self.combo_camera.blockSignals(False)
        if self.is_connected:
            # Hot-swap: AppCore spawns its own thread, don't double-thread
            self.lbl_status.setText("Trocando câmera...")
            self.core.switch_camera_live(new_cam_id)
        else:
            self.core.set_camera(new_cam_id)

    @Slot()
    def on_camera_swapped(self):
        """Called when hot-swap finishes. Resets render state to unfreeze video."""
        self.is_drawing = False
        # Clear the last frame so pull_frame won't display stale image
        try:
            self.core.video_receiver.latest_frame = None
        except Exception:
            pass

    def _toggle_mirror(self, checked: bool):
        if hasattr(self.core, 'set_mirrored'):
            self.core.set_mirrored(checked)
            self.btn_mirror.setText(" Desespelhar" if checked else " Espelhar Imagem")

    def _toggle_mic(self, checked: bool):
        self.core.set_audio_enabled(checked)
        self.audio_meter.setVisible(checked)
        self.btn_noise_reduction.setVisible(checked)
        self.btn_monitor.setVisible(checked)
        self.combo_audio_out.setVisible(checked)
        self.btn_mic.setText(" Microfone Ligado" if checked else " Ativar Microfone")
        self.btn_mic.setStyleSheet("background-color: #0d2b1e; color: #00e676;" if checked else "")
        
        # Mostrar botão de instalar VB-Cable se o cabo virtual não estiver na lista
        has_vbcable = any("CABLE" in dev.description().upper() or "VB-AUDIO" in dev.description().upper() for dev in getattr(self, '_audio_devices', []))
        self.btn_install_vbcable.setVisible(checked and not has_vbcable)
        
        # Se desligou o mic, desliga também os efeitos adicionais
        if not checked:
            self.btn_noise_reduction.setChecked(False)
            self.core.set_noise_reduction(False)
            self.btn_monitor.setChecked(False)
            self.core.set_monitoring(False)
        
        # Se já estiver conectado, reinicia o servidor para aplicar flag de áudio
        if self.is_connected:
            self.lbl_status.setText("Reiniciando para aplicar Áudio...")
            self.core.switch_camera_live(self.core.camera_id)

    def _toggle_noise_reduction(self, checked: bool):
        self.core.set_noise_reduction(checked)
        self.btn_noise_reduction.setText(" Filtro Ativo" if checked else " Redução de Ruído")
        self.btn_noise_reduction.setStyleSheet(
            "background-color: #1a1a2e; color: #64b5f6;" if checked else ""
        )

    def _toggle_monitoring(self, checked: bool):
        self.core.set_monitoring(checked)
        self.btn_monitor.setText(" Monitor Ativo" if checked else " Ouvir Retorno")
        self.btn_monitor.setStyleSheet(
            "background-color: #4a148c; color: #e1bee7;" if checked else ""
        )

    def _on_audio_out_changed(self, index: int):
        if 0 <= index < len(self._audio_devices):
            device = self._audio_devices[index]
            self.core.set_audio_device(device)


    @Slot(int)
    def _on_audio_level(self, level: int):
        if hasattr(self, 'audio_meter') and self.audio_meter.isVisible():
            self.audio_meter.set_level(level)

    def _set_rotation(self, degrees: int):
        self._rotation = degrees
        self.core.set_rotation(degrees)
        # Highlight active button
        for btn, deg in self._rot_buttons:
            btn.setStyleSheet(
                "background-color: #00c853; color: #000;" if deg == degrees
                else ""
            )

    def _auto_rotate(self):
        """Detect orientation from current frame and auto-rotate."""
        frame = self.core.video_receiver.latest_frame
        if frame is None:
            return
        try:
            # latest_frame is already a numpy RGB array
            h, w = frame.shape[:2]
            if w > h:  # Landscape frame (native) → 0° UI rotation now correctly applies the base offset to make it portrait
                self._set_rotation(0)
            else:
                # If native frame is already portrait, 0° UI rotation would make it landscape due to the base offset.
                # In this case, we need to offset the base offset.
                base_offset = 270 if self.core.camera_id == 0 else 90
                self._set_rotation((360 - base_offset) % 360)
        except Exception:
            pass

    @Slot(int, int)
    def _on_stream_info_auto_rotate(self, stream_w: int, stream_h: int):
        """Auto-rotate when stream first connects based on actual frame dimensions.
        Desativado: Agora a rotação 0° já é mapeada para a orientação vertical correta
        para ambas as câmeras (frontal e traseira).
        """
        pass

    @Slot(int, int)
    def _on_stream_info_sync_wifi_flag(self, stream_w: int, stream_h: int):
        """Sync WiFi connection flag when first frame arrives.
        This handles the case where app reconnects via config.ini (saved WiFi IP),
        which doesn't go through the WifiManager callbacks (hybrid/manual/usb_return).
        Once first frame succeeds, we know the connection type and can update the tray.
        """
        if hasattr(self, 'wifi_manager') and hasattr(self.core, 'is_connection_wireless'):
            # Detect actual connection type from device_serial ("IP:port" = WiFi, plain serial = USB)
            self.wifi_manager.is_wireless = self.core.is_connection_wireless()
            self.wifi_manager.update_menu()
            self.set_wifi_mode(self.wifi_manager.is_wireless)
            # Update bitrate limit in UI if we just switched to WiFi
            if self.wifi_manager.is_wireless:
                self.lbl_status.setText("Modo Wi-Fi")
                # Limit bitrate to 8 Mbps max on WiFi if currently higher
                if self.slider_bitrate.value() > 8:
                    self.slider_bitrate.setValue(8)

    def _on_bitrate_changed(self, val):
        if self.core.running:
            active_val = self.core.bitrate // 1_000_000
            if val != active_val:
                self.slider_bitrate.blockSignals(True)
                self.slider_bitrate.setValue(active_val)
                self.slider_bitrate.blockSignals(False)
                
                import PySide6.QtGui
                from PySide6.QtWidgets import QToolTip
                import PySide6.QtCore
                QToolTip.showText(
                    PySide6.QtGui.QCursor.pos(), 
                    "Pare a transmissão para alterar o bitrate.", 
                    self.slider_bitrate, 
                    PySide6.QtCore.QRect(), 
                    3000
                )
            return

        self.lbl_bitrate_val.setText(f"{val} Mbps")
        self.core.set_bitrate(val * 1_000_000)

    def _toggle_obs(self, checked: bool):
        if checked:
            # Garante que o Unity Capture esteja desativado antes de ativar OBS
            if self.btn_unity.isChecked():
                self.btn_unity.setChecked(False)
                self.core.disable_virtual_cam()
                self.btn_unity.setText(" Câmera Virtual (Streamlabs / Web)")
                self.lbl_unity_status.setText("Câmera Universal: inativo")
                self.lbl_unity_status.setStyleSheet("color: #444; font-size: 9px;")
            # Usa backend='obs' estrito: não cai em unitycapture mesmo que esteja instalado
            ok = self.core.enable_virtual_cam(backend="obs")
            if ok:
                self.btn_obs.setText(" Desativar Câmera Virtual")
                self.lbl_obs_status.setText("Ativo — disponível no OBS Studio")
                self.lbl_obs_status.setStyleSheet("color: #00e676; font-size: 9px; padding: 0 12px 4px 30px;")
            else:
                self.btn_obs.setChecked(False)
                self.lbl_obs_status.setText("Câmera Virtual não encontrada")
                self.lbl_obs_status.setStyleSheet("color: #ff5252; font-size: 9px; padding: 0 12px 4px 30px;")
                self._show_install_dialog()
        else:
            self.core.disable_virtual_cam()
            self.btn_obs.setText(" Ativar Câmera Virtual")
            self.lbl_obs_status.setText("OBS Virtual Camera: inativo")
            self.lbl_obs_status.setStyleSheet("color: #444; font-size: 9px;")

    def _toggle_unity(self, checked: bool):
        """Ativa/desativa o Unity Capture como câmera virtual (Experimental).
        Comportamento:
          - Driver instalado: funciona como toggle igual ao botão OBS.
          - Driver não instalado: abre dialog de instalação e, após fechar,
            tenta ativar automaticamente (se o usuário instalou).
        """
        if checked:
            # Garante que o OBS esteja desativado antes de ativar o Unity
            if self.btn_obs.isChecked():
                self.btn_obs.setChecked(False)
                self.core.disable_virtual_cam()
                self.btn_obs.setText(" Ativar Câmera Virtual")
                self.lbl_obs_status.setText("OBS Virtual Camera: inativo")
                self.lbl_obs_status.setStyleSheet("color: #444; font-size: 9px;")

            ok = self.core.enable_virtual_cam(backend="unitycapture")
            if ok:
                self.btn_unity.setText(" Desativar Câmera Universal")
                self.lbl_unity_status.setText("Ativo — Unity Video Capture")
                self.lbl_unity_status.setStyleSheet("color: #ffd54f; font-size: 9px; padding: 0 12px 4px 30px;")
            else:
                # Driver não encontrado: mantém botão desmarcado e abre instalador
                self.btn_unity.setChecked(False)
                self.lbl_unity_status.setText("Driver não instalado. Instale para usar.")
                self.lbl_unity_status.setStyleSheet("color: #ff5252; font-size: 9px; padding: 0 12px 4px 30px;")
                # Abre dialog e, se o usuário instalou, tenta ativar automaticamente ao fechar
                self._show_unity_install_dialog(try_activate_after=True)
        else:
            self.core.disable_virtual_cam()
            self.btn_unity.setText(" Câmera Virtual (Streamlabs / Web)")
            self.lbl_unity_status.setText("  Câmera Universal: inativo")
            self.lbl_unity_status.setStyleSheet("color: #444; font-size: 9px; padding: 0 12px 2px 12px;")

    def _show_unity_install_dialog(self, try_activate_after: bool = False):
        """Abre o dialog de instalação/remoção do driver Unity Capture.
        Se try_activate_after=True, tenta ativar a câmera após fechar o dialog.
        """
        from ui.install_dialog import UnityCaptureInstallDialog
        # Salva em self para não ser coletado pelo Garbage Collector
        self._unity_dlg = UnityCaptureInstallDialog(parent=self, base_path=self.core.base_path)

        if try_activate_after:
            def on_finished():
                ok = self.core.enable_virtual_cam(backend="unitycapture")
                if ok:
                    self.btn_unity.setChecked(True)
                    self.btn_unity.setText(" Desativar Câmera Universal")
                    self.lbl_unity_status.setText("Ativo — Unity Video Capture")
                    self.lbl_unity_status.setStyleSheet("color: #ffd54f; font-size: 9px; padding: 0 12px 2px 30px;")
                else:
                    self.lbl_unity_status.setText("  Driver não detectado. Reinicie o Windows e tente novamente.")
                    self.lbl_unity_status.setStyleSheet("color: #888; font-size: 9px; padding: 0 12px 2px 12px;")
            self._unity_dlg.finished.connect(on_finished)

        # open() abre como modal mas não bloqueia o event loop do ADB
        self._unity_dlg.open()


    def _toggle_camera_window(self, checked: bool):
        """Abre ou fecha a janela flutuante de câmera."""
        if checked:
            if self._camera_window is None:
                self._camera_window = CameraOnlyWindow(self.core)
                self._camera_window.closed.connect(self._on_camera_window_closed)
            self._camera_window.show()
            self._camera_window.raise_()
        else:
            if self._camera_window:
                self._camera_window.close()

    def set_wifi_mode(self, is_wireless: bool):
        """Ajusta as restrições da UI dependendo do tipo de conexão."""
        if is_wireless:
            self.slider_bitrate.setMaximum(8)
            if self.slider_bitrate.value() > 8:
                self.slider_bitrate.setValue(6)
            self.slider_bitrate.setToolTip("Modo Wi-Fi: Limitado a 8 Mbps para garantir fluidez")
        else:
            self.slider_bitrate.setMaximum(20)
            self.slider_bitrate.setToolTip("")

        # Atualiza o submenu Wi-Fi da engrenagem conforme o modo atual
        if hasattr(self, 'act_wifi_hybrid'):
            self.act_wifi_hybrid.setEnabled(not is_wireless)
            self.act_wifi_ip.setEnabled(not is_wireless)
            self.act_wifi_usb.setEnabled(is_wireless)
        
        # Atualiza label do submenu para indicar estado visual
        if hasattr(self, 'wifi_submenu'):
            if is_wireless:
                self.wifi_submenu.setTitle("  Wi-Fi Ativo")
                self.wifi_submenu.setIcon(icons.get_icon(icons.SVG_WIFI, "#00e676", 16))
            else:
                self.wifi_submenu.setTitle("  Conexão Wi-Fi")
                self.wifi_submenu.setIcon(icons.get_icon(icons.SVG_WIFI, "#ffeb3b", 16))

    def _on_camera_window_closed(self):
        """Limpa a referência e desmarca o botão quando a janela é fechada."""
        self._camera_window = None
        self.btn_camera_window.setChecked(False)

    def _show_install_dialog(self):
        from ui.install_dialog import VirtualCamInstallDialog
        self._obs_dlg = VirtualCamInstallDialog(self)
        
        def on_finished():
            # After dialog closes, update the label to guide user
            self.lbl_obs_status.setText("Após instalar, reinicie e tente novamente.")
            self.lbl_obs_status.setStyleSheet("color: #888; font-size: 9px;")
            
        self._obs_dlg.finished.connect(on_finished)
        self._obs_dlg.open()

    def _show_vbcable_install_dialog(self):
        from ui.install_dialog import VBCableInstallDialog
        self._vbcable_dlg = VBCableInstallDialog(self)
        self._vbcable_dlg.open()

    def _open_log_viewer(self):
        """Abre (ou foca) o visualizador de logs em tempo real."""
        from ui.log_viewer import LogViewerDialog
        # Reusar instância existente se ainda estiver aberta
        if self._log_viewer_dialog is not None and self._log_viewer_dialog.isVisible():
            self._log_viewer_dialog.raise_()
            self._log_viewer_dialog.activateWindow()
            return
        # Criar nova instância
        self._log_viewer_dialog = LogViewerDialog(
            log_file_path=self._log_file_path,
            parent=self
        )
        self._log_viewer_dialog.show()

    def on_start_clicked(self):
        # Setup WiFi fallback IP if not already connected to WiFi
        if not (getattr(self, 'wifi_manager', None) and self.wifi_manager.is_wireless):
            last_ip = self.settings.value("network/last_ip", "", type=str)
            if last_ip:
                self.core.wifi_fallback_ip = last_ip
        
        fps = self.combo_fps.currentData()
        self.core.set_fps(fps)
        
        # --- Sistema de Estabilidade Fluida Wi-Fi ---
        # No Wi-Fi, bitrates altos causam micro-stutters e dropped frames.
        # Limitamos o slider a 8 Mbps no máximo para Wi-Fi.
        bitrate_val = self.slider_bitrate.value()
        if getattr(self, 'wifi_manager', None) and self.wifi_manager.is_wireless:
            if bitrate_val > 8:
                self.slider_bitrate.setValue(8)
                bitrate_val = 8
            self.lbl_status.setText(f"Modo Wi-Fi ({bitrate_val} Mbps)")
        
        self.core.set_bitrate(bitrate_val * 1_000_000)
        
        res_w, res_h = self.combo_res.currentData()
        self.core.set_resolution(res_w, res_h)
        cam_id = self.combo_camera.currentData()
        self.core.set_camera(cam_id)

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_obs.setEnabled(True)
        self.btn_unity.setEnabled(True)
        self.btn_camera_window.setEnabled(True)
        self.combo_camera.setEnabled(False)
        self.combo_fps.setEnabled(False)
        self.combo_res.setEnabled(False)
        if not (getattr(self, 'wifi_manager', None) and self.wifi_manager.is_wireless and self.slider_bitrate.value() <= 8):
            self.video_widget.set_status("Conectando...")
        self.core.start_connection()

    def on_stop_clicked(self):
        self.btn_start.setEnabled(False) # Keep disabled until background cleanup finishes!
        self.btn_stop.setEnabled(False)
        self.btn_obs.setEnabled(False)
        self.btn_obs.setChecked(False)
        self.btn_obs.setText(" Ativar Câmera Virtual")
        self.lbl_obs_status.setText("OBS Virtual Camera: inativo")
        self.lbl_obs_status.setStyleSheet("color: #444; font-size: 9px;")
        # Unity Capture — desativar e resetar
        self.btn_unity.setEnabled(False)
        self.btn_unity.setChecked(False)
        self.btn_unity.setText(" Câmera Virtual (Streamlabs / Web)")
        self.lbl_unity_status.setText("  Câmera Universal: inativo  ·  clique direito para gerenciar driver")
        self.lbl_unity_status.setStyleSheet("color: #444; font-size: 9px; padding: 0 12px 4px 12px;")
        # Fechar janela de câmera se estiver aberta
        self.btn_camera_window.setEnabled(False)
        self.btn_camera_window.setChecked(False)
        if self._camera_window:
            self._camera_window.close()
        self.combo_camera.setEnabled(True)
        self.combo_fps.setEnabled(True)
        self.combo_res.setEnabled(True)
        self.is_connected = False
        self.lbl_rec.setVisible(False)
        # Limpa imagem congelada da área de vídeo
        self._last_frame_count = -1
        self.video_widget.set_status("Aguardando Câmera...")
        self.core.stop_connection()
        # Atualiza o menu Wi-Fi para refletir o estado atual
        # Se não estiver realmente transmitindo via Wi-Fi, reseta o menu
        if hasattr(self, 'wifi_manager'):
            # Se o usuário parou manualmente (não clicou em Voltar para USB),
            # mantemos is_wireless=True só para reconectar depois.
            # Mas o menu deve mostrar que a transmissão está parada.
            self.wifi_manager.update_menu()

    # ── Frame rendering ──

    @Slot()
    def pull_frame(self):
        if self.is_drawing:
            return

        frame = self.core.video_receiver.latest_frame
        cnt = self.core.video_receiver.frame_count

        if frame is None or cnt == getattr(self, '_last_frame_count', -1):
            return

        self._last_frame_count = cnt
        self.is_drawing = True

        if not self.is_connected:
            self.is_connected = True
            self.lbl_rec.setVisible(True)
            self.lbl_status.setText("Transmitindo")

        try:
            img_array = frame  # latest_frame is already a numpy RGB array
            if not img_array.flags['C_CONTIGUOUS']:
                img_array = np.ascontiguousarray(img_array)

            # Apply effective rotation
            rot = self.core.effective_rotation
            if rot == 90:
                img_array = np.rot90(img_array, k=1)  # 90° CCW
            elif rot == 180:
                img_array = np.rot90(img_array, k=2)  # 180°
            elif rot == 270:
                img_array = np.rot90(img_array, k=3)  # 90° CW

            if getattr(self.core, 'is_mirrored', False):
                img_array = np.fliplr(img_array)

            if not img_array.flags['C_CONTIGUOUS']:
                img_array = np.ascontiguousarray(img_array)

            h, w, ch = img_array.shape
            qt_img = QImage(img_array.data, w, h, ch * w, QImage.Format_RGB888)
            self.video_widget.set_image(qt_img.copy())
        except Exception as e:
            import logging
            logging.error(f"UI Frame Draw Error: {e}")
        finally:
            self.is_drawing = False

    # ── Status & Stats ──

    @Slot(str)
    def update_status(self, msg):
        self.lbl_status.setText(msg)
        
        # Check if the message is a fatal disconnect error
        # Important: Don't trigger on operational messages like "USB não encontrado. Tentando WiFi..."
        is_fatal = (
            msg.startswith("Erro:") or
            msg.startswith("Falha") or
            "interrompida" in msg or
            "Desconectado" in msg
        )
        
        if is_fatal:
            # First properly shut down the UI state and backend thread
            if self.is_connected or self.btn_stop.isEnabled():
                self.on_stop_clicked()
            
            # Now override the 'Aguardando Câmera...' message set by on_stop_clicked()
            self.lbl_status.setText(msg)
            self.video_widget.set_status(msg)
            
            # Re-enable the start button once the backend has fully disconnected
            self.btn_start.setEnabled(True)
            
            # If it was interrupted (e.g. by native Camera app), show a dialog
            if "interrompida" in msg:
                QMessageBox.warning(
                    self, 
                    "Conexão Perdida", 
                    "A transmissão foi interrompida!\n\n"
                    "Isso geralmente acontece se você abrir o aplicativo de Câmera nativo "
                    "no seu celular enquanto está transmitindo, pois o Android só permite "
                    "que um aplicativo use a lente de cada vez.\n\n"
                    "Feche a câmera no celular e tente conectar novamente."
                )

    @Slot(str, str)
    def show_warning_dialog(self, title: str, message: str):
        """Shows a warning dialog to the user."""
        QMessageBox.warning(self, title, message)

    @Slot(dict)
    def update_stats(self, stats: dict):
        fps = stats.get('fps', 0)
        self.stat_fps.set_value(f"{fps} fps")
        self.stat_fps.set_active(fps > 10)
        self.stat_res.set_value(stats.get('resolution', '---'))
        self.stat_source.set_value(stats.get('source', '---'))

        # Mostrar tipo de conexão (USB/Wi-Fi) sem informações sensíveis
        is_wireless = self.core.is_connection_wireless()
        if is_wireless:
            self.stat_device.set_value("via Wi-Fi")
            # Atualizar ícone para Wi-Fi
            self.stat_device.set_icon(icons.SVG_WIFI, "#00e676")
        else:
            self.stat_device.set_value("via USB")
            # Atualizar ícone para USB (cast)
            self.stat_device.set_icon(icons.SVG_CAST, "#00e676")

        self.stat_bitrate.set_value(f"{stats.get('bitrate_mbps', 0)} Mbps")

        # Histograma de FPS
        self.fps_sparkline.push(fps)

        # Latência
        latency = stats.get('latency_ms', None)
        if latency is not None:
            lat_str = f"{latency} ms"
            lat_ok = latency < 150
            self.stat_latency.set_value(lat_str)
            self.stat_latency.set_active(lat_ok)
        else:
            self.stat_latency.set_value('---')

    def _load_settings(self):
        try:
            fps_idx = self.settings.value("video/fps_index", 1, type=int)
            res_idx = self.settings.value("video/res_index", 2, type=int)
            bitrate = self.settings.value("video/bitrate", 8, type=int)
            cam_idx = self.settings.value("video/cam_index", 0, type=int)
            mirror = self.settings.value("video/mirror", True, type=bool)
            rotation = self.settings.value("video/rotation", 0, type=int)
            
            # Apply to UI safely
            if 0 <= fps_idx < self.combo_fps.count(): self.combo_fps.setCurrentIndex(fps_idx)
            if 0 <= res_idx < self.combo_res.count(): self.combo_res.setCurrentIndex(res_idx)
            if 2 <= bitrate <= 20: self.slider_bitrate.setValue(bitrate)
            if 0 <= cam_idx < self.combo_camera.count(): self.combo_camera.setCurrentIndex(cam_idx)
            
            audio_out_idx = self.settings.value("video/audio_out_index", -1, type=int)
            if 0 <= audio_out_idx < self.combo_audio_out.count():
                self.combo_audio_out.setCurrentIndex(audio_out_idx)
                # Força atualizar o backend se não for o índice 0 (pois o default signal pode não propagar a tempo)
                if audio_out_idx >= 0:
                    self._on_audio_out_changed(audio_out_idx)
            elif self.combo_audio_out.count() > 0:
                # Default para o primeiro dispositivo e notifica o backend
                self.combo_audio_out.setCurrentIndex(0)
                self._on_audio_out_changed(0)
            
            self.btn_mirror.setChecked(mirror)
            self._toggle_mirror(mirror)
            self._set_rotation(rotation)
        except Exception as e:
            import logging
            logging.error(f"Erro ao carregar configuracoes: {e}")

    def _save_settings(self):
        try:
            self.settings.setValue("video/fps_index", self.combo_fps.currentIndex())
            self.settings.setValue("video/res_index", self.combo_res.currentIndex())
            self.settings.setValue("video/bitrate", self.slider_bitrate.value())
            self.settings.setValue("video/cam_index", self.combo_camera.currentIndex())
            self.settings.setValue("video/audio_out_index", self.combo_audio_out.currentIndex())
            self.settings.setValue("video/mirror", self.btn_mirror.isChecked())
            self.settings.setValue("video/rotation", self._rotation)
        except Exception as e:
            import logging
            logging.error(f"Erro ao salvar configuracoes: {e}")

    def closeEvent(self, event):
        self._save_settings()
        self.core.cleanup_on_exit()  # Full cleanup including ADB server stop
        super().closeEvent(event)
