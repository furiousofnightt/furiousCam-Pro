"""
ui/camera_window.py – Janela flutuante somente câmera.

Barra de botões real no topo com:
  ✕ Fechar  |  ⛶ Fullscreen  |  Sempre no Topo  |  ↺ Girar  |  ● LIVE
Arrastar a área da câmera → Move a janela
Bordas → Redimensiona
"""

import numpy as np
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel, QVBoxLayout, QSizePolicy
)
from PySide6.QtGui import (
    QImage, QPainter, QColor, QFont, QPen, QLinearGradient, QBrush, QAction, QIcon
)
from PySide6.QtCore import Qt, QTimer, QPoint, QRect, Signal


_BTN_STYLE = """
QPushButton {{
    background: {bg};
    color: {fg};
    border: none;
    border-radius: 5px;
    padding: 4px 10px;
    font-size: 12px;
    font-weight: 600;
}}
QPushButton:hover {{
    background: {hov};
}}
"""

_TOOLBAR_STYLE = """
QWidget#toolbar {
    background-color: rgba(12, 12, 16, 210);
    border-bottom: 1px solid rgba(255,255,255,15);
}
"""


class _VideoCanvas(QWidget):
    """Sub-widget que pinta o frame da câmera."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._image: QImage | None = None
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_image(self, img: QImage):
        self._image = img
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        rect = self.rect()
        painter.fillRect(rect, QColor(0, 0, 0))

        if self._image:
            scaled = self._image.scaled(
                rect.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            x = (rect.width()  - scaled.width())  // 2
            y = (rect.height() - scaled.height()) // 2
            painter.drawImage(x, y, scaled)

            # Borda verde fina
            pen = QPen(QColor(0, 200, 83), 2)
            painter.setPen(pen)
            painter.drawRect(x, y, scaled.width() - 1, scaled.height() - 1)
        else:
            cx, cy = rect.width() // 2, rect.height() // 2
            painter.setPen(QPen(QColor(50, 50, 60), 2))
            painter.drawRoundedRect(cx - 40, cy - 28, 80, 56, 8, 8)
            painter.drawEllipse(cx - 16, cy - 16, 32, 32)
            painter.setPen(QColor(90, 90, 110))
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(rect.adjusted(0, 80, 0, 0), Qt.AlignCenter, "Aguardando stream...")


class CameraOnlyWindow(QWidget):
    """Janela flutuante sem moldura com barra de botões real no topo."""

    closed = Signal()

    _RESIZE_MARGIN = 8

    def __init__(self, core_manager, parent=None):
        super().__init__(parent)
        self.core = core_manager

        self.setWindowTitle("FuriousCam Preview")
        self.setWindowIcon(QIcon(core_manager.base_path + "/icon.ico")) if hasattr(core_manager, 'base_path') else None
        
        # O OBS Studio precisa que a janela seja um HWND nativo e sem estilos de "overlay"
        self.setAttribute(Qt.WA_NativeWindow, True)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setMinimumSize(320, 220)
        self.resize(640, 400)
        self.setStyleSheet("background-color: #000;")
        self.setMouseTracking(True)

        # ── Estado ──────────────────────────────────────────────────────────
        self._always_on_top  = True
        self._is_fullscreen  = False
        self._last_frame_cnt = -1
        self._drag_start: QPoint | None = None
        self._resize_dir: str | None = None
        self._resize_geom: QRect | None = None
        self._resize_mouse: QPoint | None = None
        self._toolbar_hidden = False
        self._last_orientation: str | None = None  # 'portrait' | 'landscape'

        # ── Layout principal ─────────────────────────────────────────────────
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Toolbar ──────────────────────────────────────────────────────────
        self._toolbar = QWidget(objectName="toolbar")
        self._toolbar.setFixedHeight(36)
        self._toolbar.setStyleSheet(_TOOLBAR_STYLE)
        tb = QHBoxLayout(self._toolbar)
        tb.setContentsMargins(8, 0, 8, 0)
        tb.setSpacing(4)

        # Badge LIVE
        self._lbl_live = QLabel("● LIVE")
        self._lbl_live.setStyleSheet(
            "color: #ff5252; font-size: 11px; font-weight: 700; padding: 0 6px;"
        )

        # Botão Girar
        self._btn_rotate = QPushButton("↺ Girar")
        self._btn_rotate.setStyleSheet(
            _BTN_STYLE.format(bg="#1a2a3a", fg="#90caf9", hov="#1e3350")
        )
        self._btn_rotate.clicked.connect(self._rotate_frame)
        self._btn_rotate.setToolTip("Girar 90°")

        # A janela agora é SEMPRE on top por padrão, botão removido.

        # Botão Fullscreen
        self._btn_fs = QPushButton("⛶ Fullscreen")
        self._btn_fs.setStyleSheet(
            _BTN_STYLE.format(bg="#1a2a1a", fg="#a5d6a7", hov="#1f361f")
        )
        self._btn_fs.clicked.connect(self._toggle_fullscreen)
        self._btn_fs.setToolTip("Clique duplo também funciona")

        # Botão Modo Fundo (Para o OBS continuar capturando)
        self._btn_bg = QPushButton("🗗 Modo Fundo")
        self._btn_bg.setStyleSheet(
            _BTN_STYLE.format(bg="#2c2c2c", fg="#e0e0e0", hov="#3d3d3d")
        )
        self._btn_bg.clicked.connect(self._send_to_background)
        self._btn_bg.setToolTip("Joga a janela para trás de todas as outras (OBS continua gravando)")

        # Botão Fechar
        self._btn_close = QPushButton("✕ Fechar")
        self._btn_close.setStyleSheet(
            _BTN_STYLE.format(bg="#2a1515", fg="#ff5252", hov="#3d1f1f")
        )
        self._btn_close.clicked.connect(self.close)

        tb.addWidget(self._lbl_live)
        tb.addStretch()
        tb.addWidget(self._btn_rotate)
        tb.addWidget(self._btn_bg)
        tb.addWidget(self._btn_fs)
        tb.addWidget(self._btn_close)

        # O botão flutuante será criado depois do canvas para ficar por cima

        # ── Canvas da câmera ─────────────────────────────────────────────────
        self._canvas = _VideoCanvas()
        self._canvas.setMouseTracking(True)
        self._canvas.mousePressEvent   = self._canvas_mouse_press
        self._canvas.mouseMoveEvent    = self._canvas_mouse_move
        self._canvas.mouseReleaseEvent = self._canvas_mouse_release
        self._canvas.mouseDoubleClickEvent = self._canvas_dbl_click

        root.addWidget(self._toolbar)
        root.addWidget(self._canvas)

        # Botão flutuante "Sair do Fullscreen" (escondido por padrão)
        self._btn_float_exit = QPushButton("⊡ Sair do Fullscreen", self)
        self._btn_float_exit.setStyleSheet(
            "background: rgba(20, 20, 30, 200); color: #fff; border: 1px solid #555; border-radius: 6px; padding: 6px 16px; font-weight: bold;"
        )
        self._btn_float_exit.setCursor(Qt.PointingHandCursor)
        self._btn_float_exit.clicked.connect(self._toggle_fullscreen)
        self._btn_float_exit.hide()

        # ── Timer de renderização ─────────────────────────────────────────────
        self._render_timer = QTimer(self)
        self._render_timer.timeout.connect(self._pull_frame)
        self._render_timer.start(33)

        # ── Rotação local (pode divergir da janela principal) ─────────────────
        self._local_rotation = getattr(core_manager, 'rotation', 0)

    # ──────────────────────────────────────────────────────────────────────────
    #  Frame rendering
    # ──────────────────────────────────────────────────────────────────────────

    def _pull_frame(self):
        frame = self.core.video_receiver.latest_frame
        cnt   = self.core.video_receiver.frame_count

        if frame is None or cnt == self._last_frame_cnt:
            return

        self._last_frame_cnt = cnt
        arr = frame
        if not arr.flags["C_CONTIGUOUS"]:
            arr = np.ascontiguousarray(arr)

        base_offset = 270 if self.core.camera_id == 0 else 90
        rot = (self._local_rotation + base_offset) % 360
        if rot == 90:
            arr = np.rot90(arr, k=1)
        elif rot == 180:
            arr = np.rot90(arr, k=2)
        elif rot == 270:
            arr = np.rot90(arr, k=3)

        if getattr(self.core, 'is_mirrored', False):
            arr = np.fliplr(arr)

        if not arr.flags["C_CONTIGUOUS"]:
            arr = np.ascontiguousarray(arr)

        h, w = arr.shape[:2]
        img = QImage(arr.data, w, h, w * 3, QImage.Format_RGB888).copy()
        self._canvas.set_image(img)
        self._adapt_window_to_frame(w, h)

    def _adapt_window_to_frame(self, frame_w: int, frame_h: int):
        """Redimensiona a janela para eliminar barras pretas, mantendo área similar."""
        if self._is_fullscreen:
            return

        orientation = 'portrait' if frame_h > frame_w else 'landscape'
        if orientation == self._last_orientation:
            return
        self._last_orientation = orientation

        # Calcula novo tamanho preservando a área total aproximada
        current_w = self.width()
        toolbar_h = self._toolbar.height() if not self._toolbar_hidden else 0
        canvas_h = max(self.height() - toolbar_h, 100)
        area = current_w * canvas_h

        aspect = frame_w / frame_h
        new_w = int((area * aspect) ** 0.5)
        new_h = int(new_w / aspect)

        # Limites mínimos e máximos razoáveis
        new_w = max(280, min(new_w, 900))
        new_h = max(200, min(new_h, 900))

        self.resize(new_w, new_h + toolbar_h)

    # ──────────────────────────────────────────────────────────────────────────
    #  Canvas mouse events (mover / redimensionar)
    # ──────────────────────────────────────────────────────────────────────────

    def _canvas_mouse_press(self, event):
        if event.button() == Qt.LeftButton and not self._is_fullscreen:
            d = self._get_resize_dir(event.globalPosition().toPoint())
            if d:
                self._resize_dir   = d
                self._resize_geom  = self.geometry()
                self._resize_mouse = event.globalPosition().toPoint()
            else:
                self._drag_start = (
                    event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                )

    def _canvas_mouse_move(self, event):
        gpos = event.globalPosition().toPoint()

        if event.buttons() & Qt.LeftButton and self._resize_dir:
            self._do_resize(gpos)
            return

        if event.buttons() & Qt.LeftButton and self._drag_start:
            self.move(gpos - self._drag_start)
            return

        if not self._is_fullscreen:
            d = self._get_resize_dir(gpos)
            self.setCursor(self._cursor_for_dir(d))

    def _canvas_mouse_release(self, event):
        self._drag_start   = None
        self._resize_dir   = None
        self._resize_geom  = None
        self._resize_mouse = None
        self.setCursor(Qt.ArrowCursor)

    def _canvas_dbl_click(self, event):
        if event.button() == Qt.LeftButton:
            self._toggle_fullscreen()

    def _get_resize_dir(self, gpos: QPoint) -> str | None:
        m  = self._RESIZE_MARGIN
        lp = self.mapFromGlobal(gpos)
        r  = self.rect()
        L = lp.x() < m;   R = lp.x() > r.width()  - m
        T = lp.y() < m;   B = lp.y() > r.height() - m
        if T and L: return "tl"
        if T and R: return "tr"
        if B and L: return "bl"
        if B and R: return "br"
        if L: return "l"
        if R: return "r"
        if T: return "t"
        if B: return "b"
        return None

    def _cursor_for_dir(self, d):
        return {
            "tl": Qt.SizeFDiagCursor, "br": Qt.SizeFDiagCursor,
            "tr": Qt.SizeBDiagCursor, "bl": Qt.SizeBDiagCursor,
            "l":  Qt.SizeHorCursor,   "r":  Qt.SizeHorCursor,
            "t":  Qt.SizeVerCursor,   "b":  Qt.SizeVerCursor,
        }.get(d, Qt.OpenHandCursor)

    def _do_resize(self, gpos: QPoint):
        dx = gpos.x() - self._resize_mouse.x()
        dy = gpos.y() - self._resize_mouse.y()
        g  = self._resize_geom
        ng = QRect(g)
        d  = self._resize_dir
        if "l" in d: ng.setLeft(min(g.left() + dx, g.right() - 320))
        if "r" in d: ng.setRight(max(g.right() + dx, g.left() + 320))
        if "t" in d: ng.setTop(min(g.top() + dy, g.bottom() - 220))
        if "b" in d: ng.setBottom(max(g.bottom() + dy, g.top() + 220))
        self.setGeometry(ng)

    # ──────────────────────────────────────────────────────────────────────────
    #  Buttons
    # ──────────────────────────────────────────────────────────────────────────

    def _rotate_frame(self):
        """Gira o frame +90° a cada clique (só afeta esta janela)."""
        self._local_rotation = (self._local_rotation + 90) % 360
        # Sync de volta para o core para que a janela principal também gire
        if hasattr(self.core, 'set_rotation'):
            self.core.set_rotation(self._local_rotation)



    def _send_to_background(self):
        """Remove o 'Sempre no Topo' e joga a janela para trás de todas as outras."""
        flags = Qt.Window | Qt.FramelessWindowHint
        self.setWindowFlags(flags)
        self.show()
        self.lower()  # Joga para o fundo
        # O botão agora vira um "Voltar ao Topo"
        self._btn_bg.setText("Fixar no Topo")
        self._btn_bg.clicked.disconnect()
        self._btn_bg.clicked.connect(self._bring_to_front)

    def _bring_to_front(self):
        """Restaura o 'Sempre no Topo'."""
        flags = Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()
        self.raise_()
        self._btn_bg.setText("🗗 Modo Fundo")
        self._btn_bg.clicked.disconnect()
        self._btn_bg.clicked.connect(self._send_to_background)

    def _toggle_fullscreen(self):
        flags = Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        if self._is_fullscreen:
            self._toolbar.setVisible(True)
            self._btn_float_exit.hide()
            self.showNormal()
            self._btn_fs.setText("⛶ Fullscreen")
            self._is_fullscreen = False
        else:
            self._toolbar.setVisible(False)
            self._btn_float_exit.show()
            self._btn_float_exit.raise_()
            self.showFullScreen()
            self._btn_fs.setText("⊡ Sair Full")
            self._is_fullscreen = True

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Posicionar o botão flutuante no topo, centralizado
        btn_w = 160
        btn_h = 36
        self._btn_float_exit.setGeometry(
            (self.width() - btn_w) // 2,
            20,
            btn_w,
            btn_h
        )

    def keyPressEvent(self, event):
        """Esc sai do fullscreen."""
        if event.key() == Qt.Key_Escape and self._is_fullscreen:
            self._toggle_fullscreen()

    # ──────────────────────────────────────────────────────────────────────────
    #  Lifecycle
    # ──────────────────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        self._render_timer.stop()
        self.closed.emit()
        super().closeEvent(event)
