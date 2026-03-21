"""Excel file importer."""

import logging
import pandas as pd
from .base_importer import BaseImporter

logger = logging.getLogger(__name__)


class ExcelImporter(BaseImporter):
    """Importador de archivos Excel."""
    
    def __init__(self, file_path, table_name, sheet_name=0):
        """
        Inicializar importador Excel.
        
        Args:
            file_path: Ruta del archivo Excel
            table_name: Nombre de la tabla
            sheet_name: Nombre o índice de la hoja
        """
        super().__init__(file_path, table_name)
        self.sheet_name = sheet_name
    
    def read_file(self):
        """Leer archivo Excel."""
        try:
            df = pd.read_excel(self.file_path, sheet_name=self.sheet_name)
            self.data = df.to_dict('records')
            logger.info(f"Excel leído: {len(self.data)} filas")
            return True
        except Exception as e:
            logger.error(f"Error leyendo Excel: {e}")
            self.add_error(f"Error leyendo archivo: {str(e)}")
            return False
    
    def validate_data(self):
        """Validar datos del Excel."""
        if not self.data:
            self.add_error("No hay datos en el archivo Excel")
            return False
        
        # Validar que no haya valores nulos en columnas críticas
        for i, row in enumerate(self.data):
            for key, value in row.items():
                if pd.isna(value):
                    self.add_error(f"Fila {i+1}, Columna {key}: valor vacío")
        
        return len(self.errors) == 0
