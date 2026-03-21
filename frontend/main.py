"""Aplicación de escritorio principal."""

import sys
import logging
from PyQt5.QtWidgets import QApplication
from ui.main_window import MainWindow

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Función principal."""
    logger.info("Iniciando Database Manager GUI")
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
