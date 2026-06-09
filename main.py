import sys
import os
import logging
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
from core.app_core import AppCore

# Configuração inicial de logging (console apenas)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

def get_base_path():
    """Get base path handling both PyInstaller bundle and development mode."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller executable
        return os.path.dirname(sys.executable)
    else:
        # Running as script
        return os.path.dirname(os.path.abspath(__file__))

def setup_file_logging(base_path):
    """Configura logging para arquivo (reescrito a cada execução)."""
    log_file = os.path.join(base_path, "furiouscam.log")
    
    # Cria FileHandler que reescreve a cada execução (mode='w')
    file_handler = logging.FileHandler(log_file, mode='w')
    file_handler.setLevel(logging.INFO)
    
    # Mesmo formato do console
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    file_handler.setFormatter(formatter)
    
    # Adiciona ao logger raiz
    logging.getLogger().addHandler(file_handler)
    
    return log_file

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("FuriousCam Pro")
    app.setApplicationVersion("2.0")

    base_path = get_base_path()
    
    # Configura logging em arquivo
    log_file = setup_file_logging(base_path)
    logger = logging.getLogger(__name__)
    logger.info(f"FuriousCam Pro v2.0 iniciado. Logs: {log_file}")

    core = AppCore(base_path)
    window = MainWindow(core, log_file_path=log_file)  # signals connected inside MainWindow.__init__
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
