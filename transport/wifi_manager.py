import logging
import time
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QInputDialog, QMessageBox, QApplication
from PySide6.QtGui import QIcon
from ui import icons
from core.app_core import AppCore

logger = logging.getLogger(__name__)

class WifiManager(QObject):
    hybrid_finished = Signal(bool, str)
    manual_ip_finished = Signal(bool, str)
    usb_return_finished = Signal()

    def __init__(self, app_core: AppCore, main_window, parent=None):
        super().__init__(parent)
        self.app_core = app_core
        self.main_window = main_window
        self.is_wireless = False
        self.connected_ip = None

        # Setup System Tray
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(icons.get_icon(icons.SVG_CAST, "#00e676", 32))
        self.tray_icon.setToolTip("FuriousCam Pro - Wi-Fi Manager")

        self.menu = QMenu()
        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.show()
        self.tray_icon.activated.connect(self._on_tray_activated)

        self.update_menu()

        # Connect result signals to UI handlers (must be in __init__, not in slots)
        self.hybrid_finished.connect(self._on_hybrid_finished)
        self.manual_ip_finished.connect(self._on_manual_ip_finished)
        self.usb_return_finished.connect(self._on_usb_return_finished)

    @Slot(QSystemTrayIcon.ActivationReason)
    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:  # Left click
            rect = self.tray_icon.geometry()
            menu = self.tray_icon.contextMenu()
            menu.adjustSize()
            menu_size = menu.sizeHint()
            from PySide6.QtCore import QPoint
            x = rect.center().x() - (menu_size.width() // 2)
            y = rect.top() - menu_size.height() - 4
            menu.popup(QPoint(x, y))

    def update_menu(self):
        self.menu.clear()

        if self.is_wireless:
            title_action = self.menu.addAction(
                icons.get_icon(icons.SVG_WIFI, "#00e676", 16), "  Wi-Fi ATIVO"
            )
            title_action.setEnabled(False)
            self.menu.addSeparator()
            action_usb = self.menu.addAction("Voltar para Cabo USB")
            action_usb.triggered.connect(self.action_return_to_usb)
            action_ip = self.menu.addAction("Trocar Endereço IP Manualmente")
            action_ip.triggered.connect(self.action_connect_ip_manual)
        else:
            title_action = self.menu.addAction(
                icons.get_icon(icons.SVG_CAST, "#c0c0d0", 16), "MODO USB ATIVO"
            )
            title_action.setEnabled(False)
            self.menu.addSeparator()
            action_hybrid = self.menu.addAction("Ativar Wi-Fi (Modo Híbrido Automático)")
            action_hybrid.triggered.connect(self.action_hybrid_mode)
            action_ip = self.menu.addAction("Conectar por Endereço IP")
            action_ip.triggered.connect(self.action_connect_ip_manual)

        self.menu.addSeparator()
        action_exit = self.menu.addAction("Sair")
        action_exit.triggered.connect(QApplication.instance().quit)

    def _lock_ui(self):
        self.main_window.btn_settings.setEnabled(False)
        self.main_window.btn_start.setEnabled(False)

    def _unlock_ui(self):
        self.main_window.btn_settings.setEnabled(True)
        self.main_window.btn_start.setEnabled(True)

    # ── Hybrid Mode ────────────────────────────────────────────
    @Slot()
    def action_hybrid_mode(self):
        self.main_window.video_widget.set_status("Iniciando Transição Wi-Fi...\nAguarde cerca de 4 segundos.")
        self._lock_ui()
        import threading
        threading.Thread(target=self._hybrid_task, daemon=True).start()

    def _hybrid_task(self):
        was_running = self.app_core.running
        if was_running:
            self.app_core.stop_connection()
            time.sleep(1.0)

        self.app_core.adb_manager.start_server()
        if not self.app_core.adb_manager.wait_for_device():
            self.hybrid_finished.emit(False, "Conecte o dispositivo via cabo USB primeiro.")
            return

        ip = self.app_core.adb_manager.get_device_ip()
        if not ip:
            self.hybrid_finished.emit(False, "Não foi possível detectar o IP. O Wi-Fi está ligado?")
            return

        ip_with_port = f"{ip}:5555"
        self.app_core.connection_status.emit("Ativando ADB TCP/IP...")
        if not self.app_core.adb_manager.enable_tcpip():
            self.hybrid_finished.emit(False, "Falha ao ativar o TCP/IP.")
            return

        time.sleep(3.0)

        self.app_core.connection_status.emit(f"Conectando ao IP {ip_with_port}...")
        if self.app_core.adb_manager.connect_direct_ip(ip_with_port):
            self.hybrid_finished.emit(True, ip_with_port)
        else:
            self.hybrid_finished.emit(False, f"Falha ao conectar ao IP {ip_with_port}.")

    @Slot(bool, str)
    def _on_hybrid_finished(self, success: bool, result: str):
        self._unlock_ui()
        if success:
            self.is_wireless = True
            self.connected_ip = result
            self.app_core.wifi_fallback_ip = result  # Persiste para reconexão via Stop+Iniciar
            self.main_window.settings.setValue("network/last_ip", result)
            self.update_menu()
            self.main_window.set_wifi_mode(True)
            self.app_core.connect_via_wifi_serial(result)
            self.main_window.on_start_clicked()
            QMessageBox.information(self.main_window, "Wi-Fi Ativado",
                                    f"Conectado a {result}.\n\nVocê já pode remover o cabo USB!")
        else:
            self.main_window.video_widget.set_status("Falha na Transição Wi-Fi")
            QMessageBox.warning(self.main_window, "Erro", result)

    # ── Manual IP ──────────────────────────────────────────────
    @Slot()
    def action_connect_ip_manual(self):
        last_ip = self.main_window.settings.value("network/last_ip", "", type=str)
        ip, ok = QInputDialog.getText(self.main_window, "Conectar por IP", "Digite o IP (ex: 192.168.1.15):", text=last_ip)
        if ok and ip:
            self.main_window.video_widget.set_status(f"Conectando ao IP {ip}...")
            self._lock_ui()
            import threading
            threading.Thread(target=self._manual_ip_task, args=(ip,), daemon=True).start()

    def _manual_ip_task(self, ip: str):
        was_running = self.app_core.running
        if was_running:
            self.app_core.stop_connection()
            time.sleep(1.0)

        self.app_core.adb_manager.start_server()
        ip_with_port = ip if ":" in ip else f"{ip}:5555"

        # Verifica rapidamente se há um dispositivo USB disponível (sem esperar 5s)
        def _has_usb_device():
            try:
                result = self.app_core.adb_manager.run_adb("devices", check=False)
                for line in result.stdout.strip().split('\n')[1:]:
                    if 'device' in line and ':' not in line.split()[0] and 'unauthorized' not in line:
                        return True
            except Exception:
                pass
            return False

        if _has_usb_device():
            self.app_core.connection_status.emit("Ativando modo sem fio no dispositivo...")
            self.app_core.adb_manager.enable_tcpip()
            time.sleep(2.0)  # Aguarda o dispositivo reiniciar a escuta na porta 5555

        self.app_core.connection_status.emit(f"Conectando ao IP {ip_with_port}...")

        if self.app_core.adb_manager.connect_direct_ip(ip_with_port):
            self.manual_ip_finished.emit(True, ip_with_port)
        else:
            self.manual_ip_finished.emit(False, f"Falha ao conectar ao IP {ip_with_port}.")

    @Slot(bool, str)
    def _on_manual_ip_finished(self, success: bool, result: str):
        self._unlock_ui()
        if success:
            self.is_wireless = True
            self.connected_ip = result
            self.app_core.wifi_fallback_ip = result  # Persiste para reconexão via Stop+Iniciar
            self.main_window.settings.setValue("network/last_ip", result)
            self.update_menu()
            self.main_window.set_wifi_mode(True)
            self.app_core.connect_via_wifi_serial(result)
            self.main_window.on_start_clicked()
            self.tray_icon.showMessage("FuriousCam Pro", f"Conectado via Wi-Fi: {result}",
                                       QSystemTrayIcon.Information, 3000)
            QMessageBox.information(self.main_window, "Wi-Fi Ativado",
                                    f"Conectado a {result}.\n\nVocê já pode remover o cabo USB!")
        else:
            self.main_window.video_widget.set_status("Falha na Conexão")
            QMessageBox.warning(self.main_window, "Erro", result)

    # ── Return to USB ──────────────────────────────────────────
    @Slot()
    def action_return_to_usb(self):
        self.main_window.video_widget.set_status("Voltando para Cabo USB...")
        self._lock_ui()
        import threading
        threading.Thread(target=self._return_to_usb_task, daemon=True).start()

    def _return_to_usb_task(self):
        was_running = self.app_core.running
        if was_running:
            self.app_core.stop_connection()
            time.sleep(1.0)

        if self.connected_ip:
            self.app_core.adb_manager.disconnect_ip(self.connected_ip)

        self.usb_return_finished.emit()

    @Slot()
    def _on_usb_return_finished(self):
        self.is_wireless = False
        self.connected_ip = None
        self.app_core.wifi_fallback_ip = None  # Zera o fallback ao voltar para USB
        self.app_core.adb_manager.device_serial = None
        self.update_menu()
        self.main_window.set_wifi_mode(False)
        self._unlock_ui()
        
        # Tenta reconectar automaticamente via USB
        self.main_window.on_start_clicked()
        
        self.tray_icon.showMessage(
            "FuriousCam Pro",
            "Voltou para Cabo USB. Reconectando...",
            QSystemTrayIcon.Information,
            3000
        )

