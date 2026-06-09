import os
import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QPlainTextEdit, QFrame, QLineEdit, QCheckBox,
    QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QFont, QTextCharFormat, QColor, QTextCursor, QTextDocument, QKeySequence, QShortcut
import ui.icons as icons

logger = logging.getLogger(__name__)


class LogViewerDialog(QDialog):
    """
    Janela de visualização de logs em tempo real do FuriousCam Pro.

    Lê o arquivo furiouscam.log do disco a cada segundo,
    exibindo o conteúdo com syntax-highlight por nível de log.
    Suporta busca inline, auto-scroll e cópia para clipboard.
    """

    # Cores por nível de log
    _LEVEL_COLORS = {
        "[ERROR]":    "#ff5252",
        "[WARNING]":  "#ffb74d",
        "[INFO]":     "#80cbc4",
        "[DEBUG]":    "#888899",
    }

    def __init__(self, log_file_path: str, parent=None):
        super().__init__(parent)
        self._log_path = log_file_path
        self._last_size = -1          # Detecta mudanças sem reler tudo
        self._auto_scroll = True

        self.setWindowTitle("FuriousCam Pro — Visualizador de Logs")
        self.setMinimumSize(820, 520)
        self.resize(940, 600)
        self.setModal(False)          # Não bloqueia a janela principal
        self._apply_style()
        self._build_ui()
        self._setup_shortcuts()

        # Timer de refresh — 1s
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(1000)

        # Leitura inicial imediata
        self._refresh(force=True)

    # ─────────────────────────────────────────────
    #  Estilo
    # ─────────────────────────────────────────────
    def _apply_style(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #0d0d10;
                color: #e0e0e0;
            }
            QFrame#toolbar {
                background-color: #111116;
                border-bottom: 1px solid #222228;
            }
            QFrame#statusBar {
                background-color: #0f0f13;
                border-top: 1px solid #1a1a22;
            }
            QPlainTextEdit {
                background-color: #080810;
                color: #c8c8d8;
                border: none;
                font-family: 'Cascadia Code', 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                line-height: 1.5;
                selection-background-color: #1a3a4a;
            }
            QLineEdit {
                background-color: #1a1a22;
                color: #d0d0e0;
                border: 1px solid #2a2a38;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                min-width: 220px;
            }
            QLineEdit:focus {
                border-color: #00e676;
            }
            QLineEdit#searchNoMatch {
                border-color: #ff5252;
            }
            QPushButton#btnAction {
                background-color: #1a1a22;
                color: #c0c0d0;
                border: 1px solid #2a2a38;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#btnAction:hover {
                background-color: #1e2028;
                border-color: #00e676;
                color: #00e676;
            }
            QPushButton#btnAction:pressed {
                background-color: #0d2b1e;
            }
            QPushButton#btnDanger {
                background-color: transparent;
                color: #ff7070;
                border: 1px solid #3a2222;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#btnDanger:hover {
                background-color: #2a1010;
                border-color: #ff5252;
            }
            QCheckBox {
                color: #888;
                font-size: 11px;
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border: 1px solid #2a2a38;
                border-radius: 3px;
                background: #1a1a22;
            }
            QCheckBox::indicator:checked {
                background: #00e676;
                border-color: #00e676;
            }
            QScrollBar:vertical {
                background: #111116;
                width: 8px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #2a2a35;
                min-height: 30px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover { background: #00c853; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)

    # ─────────────────────────────────────────────
    #  UI
    # ─────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Toolbar ──
        toolbar = QFrame(objectName="toolbar")
        toolbar.setFixedHeight(50)
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(14, 0, 14, 0)
        tb.setSpacing(10)

        # Ícone + título
        icon_lbl = QLabel()
        icon_lbl.setPixmap(icons.get_icon(icons.SVG_ACTIVITY, "#00e676", 18).pixmap(18, 18))
        tb.addWidget(icon_lbl)

        title = QLabel("Logs em Tempo Real")
        title.setStyleSheet("color: #00e676; font-size: 13px; font-weight: 700; letter-spacing: 0.5px;")
        tb.addWidget(title)
        tb.addSpacing(20)

        # Ícone de lupa SVG ao lado do campo de busca
        search_icon_lbl = QLabel()
        search_icon_lbl.setPixmap(icons.get_icon(icons.SVG_SEARCH, "#00e676", 16).pixmap(16, 16))
        tb.addWidget(search_icon_lbl)

        # Campo de busca
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Buscar nos logs...  (Ctrl+F)")
        self._search_input.textChanged.connect(self._on_search_changed)
        tb.addWidget(self._search_input)

        # Prev / Next para busca
        self._btn_prev = QPushButton(objectName="btnAction")
        self._btn_prev.setIcon(icons.get_icon(icons.SVG_ARROW_UP, "#c0c0d0", 14))
        self._btn_prev.setFixedSize(30, 32)
        self._btn_prev.setToolTip("Anterior (Shift+Enter)")
        self._btn_prev.clicked.connect(self._search_prev)
        tb.addWidget(self._btn_prev)

        self._btn_next = QPushButton(objectName="btnAction")
        self._btn_next.setIcon(icons.get_icon(icons.SVG_ARROW_DOWN, "#c0c0d0", 14))
        self._btn_next.setFixedSize(30, 32)
        self._btn_next.setToolTip("Próximo (Enter)")
        self._btn_next.clicked.connect(self._search_next)
        tb.addWidget(self._btn_next)

        tb.addStretch()

        # Auto-scroll checkbox
        self._chk_autoscroll = QCheckBox("Auto-scroll")
        self._chk_autoscroll.setChecked(True)
        self._chk_autoscroll.stateChanged.connect(self._on_autoscroll_changed)
        tb.addWidget(self._chk_autoscroll)

        tb.addSpacing(8)

        # Botão atualizar
        btn_refresh = QPushButton("  Atualizar", objectName="btnAction")
        btn_refresh.setIcon(icons.get_icon(icons.SVG_ROTATE, "#00e676", 14))
        btn_refresh.setToolTip("Recarregar logs (F5)")
        btn_refresh.clicked.connect(lambda: self._refresh(force=True))
        tb.addWidget(btn_refresh)

        # Botão copiar
        btn_copy = QPushButton("  Copiar Tudo", objectName="btnAction")
        btn_copy.setIcon(icons.get_icon(icons.SVG_LAYERS, "#90caf9", 14))
        btn_copy.setToolTip("Copiar todo o conteúdo para o clipboard")
        btn_copy.clicked.connect(self._copy_all)
        tb.addWidget(btn_copy)

        # Botão limpar visualização
        btn_clear = QPushButton("  Limpar", objectName="btnDanger")
        btn_clear.setIcon(icons.get_icon(icons.SVG_STOP, "#ff7070", 14))
        btn_clear.setToolTip("Limpar a visualização (não apaga o arquivo)")
        btn_clear.clicked.connect(self._clear_view)
        tb.addWidget(btn_clear)

        root.addWidget(toolbar)

        # ── Log Display ──
        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumBlockCount(5000)   # Limite de linhas para performance
        self._log_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        # Desabilita scroll automático nativo; usamos o nosso
        self._log_view.verticalScrollBar().rangeChanged.connect(self._on_scroll_range_changed)
        root.addWidget(self._log_view, stretch=1)

        # ── Status Bar ──
        status_bar = QFrame(objectName="statusBar")
        status_bar.setFixedHeight(28)
        sb = QHBoxLayout(status_bar)
        sb.setContentsMargins(14, 0, 14, 0)
        sb.setSpacing(12)

        self._lbl_file = QLabel()
        self._lbl_file.setStyleSheet("color: #444; font-size: 10px;")
        sb.addWidget(self._lbl_file)

        sb.addStretch()

        self._lbl_lines = QLabel("0 linhas")
        self._lbl_lines.setStyleSheet("color: #444; font-size: 10px;")
        sb.addWidget(self._lbl_lines)

        self._lbl_match = QLabel("")
        self._lbl_match.setStyleSheet("color: #ffb74d; font-size: 10px;")
        sb.addWidget(self._lbl_match)

        root.addWidget(status_bar)

        # Atualizar path na status bar
        self._lbl_file.setText(f"Arquivo: {self._log_path}")

    # ─────────────────────────────────────────────
    #  Shortcuts
    # ─────────────────────────────────────────────
    def _setup_shortcuts(self):
        QShortcut(QKeySequence("F5"), self, activated=lambda: self._refresh(force=True))
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self._focus_search)
        QShortcut(QKeySequence("Ctrl+C"), self._log_view)  # Cópia de seleção já nativa
        QShortcut(QKeySequence("Escape"), self, activated=self.close)
        # Enter no campo de busca: avançar
        self._search_input.returnPressed.connect(self._search_next)

    def _focus_search(self):
        self._search_input.setFocus()
        self._search_input.selectAll()

    # ─────────────────────────────────────────────
    #  Leitura de arquivo
    # ─────────────────────────────────────────────
    def _refresh(self, force: bool = False):
        """
        Lê o arquivo de log e atualiza o display.
        Só relê se o arquivo mudou de tamanho (evita redesenho desnecessário).
        """
        if not os.path.exists(self._log_path):
            self._log_view.setPlainText(
                f"Arquivo não encontrado:\n{self._log_path}\n\n"
                "O log é criado automaticamente quando o app inicia."
            )
            self._lbl_lines.setText("—")
            return

        try:
            current_size = os.path.getsize(self._log_path)
        except OSError:
            return

        if not force and current_size == self._last_size:
            return  # Nada mudou

        self._last_size = current_size

        try:
            with open(self._log_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError as e:
            logger.warning(f"LogViewer: erro ao ler {self._log_path}: {e}")
            return

        # Renderiza com cores por nível
        self._render_colored(content)

        line_count = content.count("\n")
        self._lbl_lines.setText(f"{line_count} linhas")

        # Re-aplicar busca se houver termo ativo
        if self._search_input.text():
            self._highlight_search(self._search_input.text())

    def _render_colored(self, content: str):
        """Aplica syntax-highlight por nível de log usando QTextCharFormat."""
        self._log_view.clear()
        cursor = self._log_view.textCursor()
        cursor.movePosition(QTextCursor.End)

        default_fmt = QTextCharFormat()
        default_fmt.setForeground(QColor("#9090a0"))

        for line in content.splitlines(keepends=True):
            # Detectar nível pelo conteúdo da linha
            fmt = QTextCharFormat(default_fmt)
            for token, color in self._LEVEL_COLORS.items():
                if token in line:
                    fmt.setForeground(QColor(color))
                    if token == "[ERROR]":
                        fmt.setFontWeight(700)
                    break

            cursor.insertText(line, fmt)

        self._log_view.setTextCursor(cursor)

        if self._auto_scroll:
            self._log_view.verticalScrollBar().setValue(
                self._log_view.verticalScrollBar().maximum()
            )

    # ─────────────────────────────────────────────
    #  Auto-scroll
    # ─────────────────────────────────────────────
    def _on_scroll_range_changed(self, _min, _max):
        if self._auto_scroll:
            self._log_view.verticalScrollBar().setValue(_max)

    def _on_autoscroll_changed(self, state):
        self._auto_scroll = (state == Qt.Checked)

    # ─────────────────────────────────────────────
    #  Busca inline
    # ─────────────────────────────────────────────
    def _on_search_changed(self, text: str):
        self._lbl_match.setText("")
        # Limpar highlights anteriores
        self._clear_search_highlight()
        if text:
            count = self._highlight_search(text)
            if count == 0:
                self._search_input.setObjectName("searchNoMatch")
                self._lbl_match.setText("Não encontrado")
                self._lbl_match.setStyleSheet("color: #ff5252; font-size: 10px;")
            else:
                self._search_input.setObjectName("")
                self._lbl_match.setText(f"{count} ocorrência{'s' if count != 1 else ''}")
                self._lbl_match.setStyleSheet("color: #ffb74d; font-size: 10px;")
            self._search_input.setStyleSheet("")  # Force restyle via objectName

    def _highlight_search(self, text: str) -> int:
        """Destaca todas as ocorrências do texto. Retorna contagem."""
        if not text:
            return 0

        highlight_fmt = QTextCharFormat()
        highlight_fmt.setBackground(QColor("#2a3a10"))
        highlight_fmt.setForeground(QColor("#e6ff80"))

        doc = self._log_view.document()
        cursor = QTextCursor(doc)
        count = 0

        while True:
            cursor = doc.find(text, cursor)  # sem flags = forward
            if cursor.isNull():
                break
            cursor.mergeCharFormat(highlight_fmt)
            count += 1

        return count

    def _clear_search_highlight(self):
        """Remove todos os highlights de busca restaurando cor base."""
        doc = self._log_view.document()
        cursor = QTextCursor(doc)
        cursor.select(QTextCursor.SelectionType.Document)
        fmt = QTextCharFormat()
        fmt.setBackground(QColor("transparent"))
        cursor.mergeCharFormat(fmt)

    def _search_next(self):
        text = self._search_input.text()
        if not text:
            return
        found = self._log_view.find(text)
        if not found:
            # Wrap around: volta ao início e tenta de novo
            cursor = self._log_view.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            self._log_view.setTextCursor(cursor)
            self._log_view.find(text)

    def _search_prev(self):
        text = self._search_input.text()
        if not text:
            return
        found = self._log_view.find(text, QTextDocument.FindFlag.FindBackward)
        if not found:
            # Wrap around: vai ao final e tenta de novo
            cursor = self._log_view.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self._log_view.setTextCursor(cursor)
            self._log_view.find(text, QTextDocument.FindFlag.FindBackward)

    # ─────────────────────────────────────────────
    #  Ações dos botões
    # ─────────────────────────────────────────────
    def _copy_all(self):
        from PySide6.QtWidgets import QApplication
        text = self._log_view.toPlainText()
        QApplication.clipboard().setText(text)
        self._lbl_match.setText("✓ Copiado!")
        self._lbl_match.setStyleSheet("color: #00e676; font-size: 10px;")
        QTimer.singleShot(2000, lambda: self._lbl_match.setText(""))

    def _clear_view(self):
        """Limpa apenas a visualização — não apaga o arquivo em disco."""
        self._log_view.clear()
        self._lbl_lines.setText("0 linhas")
        self._last_size = -1  # Força releitura no próximo refresh

    # ─────────────────────────────────────────────
    #  Ciclo de vida
    # ─────────────────────────────────────────────
    def closeEvent(self, event):
        self._timer.stop()
        super().closeEvent(event)
