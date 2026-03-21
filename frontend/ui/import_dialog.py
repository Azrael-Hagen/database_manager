"""Diálogo de importación de archivos."""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QLineEdit, QFileDialog, QProgressBar, QTextEdit
)
from PyQt5.QtCore import Qt


class ImportDialog(QWidget):
    """Diálogo para importar archivos."""
    
    def __init__(self):
        """Inicializar diálogo de importación."""
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        """Inicializar interfaz."""
        layout = QVBoxLayout(self)
        
        # Seleccionar archivo
        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel("Archivo:"))
        self.file_input = QLineEdit()
        self.file_input.setReadOnly(True)
        file_layout.addWidget(self.file_input)
        browse_btn = QPushButton("Examinar...")
        browse_btn.clicked.connect(self.browse_file)
        file_layout.addWidget(browse_btn)
        layout.addLayout(file_layout)
        
        # Tipo de archivo
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Tipo de Archivo:"))
        self.file_type_combo = QComboBox()
        self.file_type_combo.addItems(["CSV", "Excel", "TXT", "DAT"])
        self.file_type_combo.currentTextChanged.connect(self.on_file_type_changed)
        type_layout.addWidget(self.file_type_combo)
        layout.addLayout(type_layout)
        
        # Delimitador
        delim_layout = QHBoxLayout()
        delim_layout.addWidget(QLabel("Delimitador:"))
        self.delimiter_combo = QComboBox()
        self.delimiter_combo.addItems([",", ";", "\t", "|", " "])
        delim_layout.addWidget(self.delimiter_combo)
        layout.addLayout(delim_layout)
        
        # Tabla destino
        table_layout = QHBoxLayout()
        table_layout.addWidget(QLabel("Tabla Destino:"))
        self.table_input = QLineEdit()
        self.table_input.setPlaceholderText("ej: datos_importados")
        table_layout.addWidget(self.table_input)
        layout.addLayout(table_layout)
        
        # Botones
        btn_layout = QHBoxLayout()
        import_btn = QPushButton("Importar")
        import_btn.clicked.connect(self.import_file)
        btn_layout.addWidget(import_btn)
        
        preview_btn = QPushButton("Vista Previa")
        preview_btn.clicked.connect(self.preview_file)
        btn_layout.addWidget(preview_btn)
        layout.addLayout(btn_layout)
        
        # Barra de progreso
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Área de registro
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("Registro de importación")
        layout.addWidget(self.log_text)
        
        layout.addStretch()
    
    def browse_file(self):
        """Buscar archivo."""
        file_filter = "Todos (*);;CSV (*.csv);;Excel (*.xlsx);;Texto (*.txt);;DAT (*.dat)"
        filename, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Archivo", "", file_filter
        )
        if filename:
            self.file_input.setText(filename)
    
    def on_file_type_changed(self):
        """Cambio de tipo de archivo."""
        file_type = self.file_type_combo.currentText()
        if file_type == "CSV":
            self.delimiter_combo.setCurrentIndex(0)  # Coma
        elif file_type == "TXT" or file_type == "DAT":
            self.delimiter_combo.setCurrentIndex(2)  # Tab
    
    def preview_file(self):
        """Mostrar vista previa del archivo."""
        self.log_text.append("Vista previa no implementada aún")
    
    def import_file(self):
        """Importar archivo."""
        self.log_text.append("Importación no implementada aún")
