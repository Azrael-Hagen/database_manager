"""Ventana principal de la aplicación."""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTabWidget, QLabel, QMenuBar, QMenu, QDialog, QFileDialog
)
from PyQt5.QtCore import Qt
from .import_dialog import ImportDialog
from .data_viewer import DataViewer


class MainWindow(QMainWindow):
    """Ventana principal de la aplicación."""
    
    def __init__(self):
        """Inicializar ventana principal."""
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        """Inicializar interfaz de usuario."""
        self.setWindowTitle("Database Manager - Gestor de Base de Datos")
        self.setGeometry(100, 100, 1000, 700)
        
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout principal
        layout = QVBoxLayout(central_widget)
        
        # Crear pestañas
        tabs = QTabWidget()
        
        # Pestaña de Datos
        self.data_viewer = DataViewer()
        tabs.addTab(self.data_viewer, "Visualizar Datos")
        
        # Pestaña de Importación
        self.import_dialog = ImportDialog()
        tabs.addTab(self.import_dialog, "Importar Datos")
        
        layout.addWidget(tabs)
        
        # Crear barra de menú
        self.create_menu_bar()
    
    def create_menu_bar(self):
        """Crear barra de menú."""
        menubar = self.menuBar()
        
        # Menú Archivo
        file_menu = menubar.addMenu("Archivo")
        
        import_action = file_menu.addAction("Importar Archivo")
        import_action.triggered.connect(self.show_import_dialog)
        
        exit_action = file_menu.addAction("Salir")
        exit_action.triggered.connect(self.close)
        
        # Menú Herramientas
        tools_menu = menubar.addMenu("Herramientas")
        
        settings_action = tools_menu.addAction("Configuración")
        settings_action.triggered.connect(self.show_settings)
        
        # Menú Ayuda
        help_menu = menubar.addMenu("Ayuda")
        about_action = help_menu.addAction("Acerca de")
        about_action.triggered.connect(self.show_about)
    
    def show_import_dialog(self):
        """Mostrar diálogo de importación."""
        self.import_dialog.show()
    
    def show_settings(self):
        """Mostrar configuración."""
        # Implementar más adelante
        pass
    
    def show_about(self):
        """Mostrar información acerca de."""
        # Implementar más adelante
        pass
