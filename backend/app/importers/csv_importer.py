"""CSV file importer."""

import csv
import logging
from .base_importer import BaseImporter

logger = logging.getLogger(__name__)


class CSVImporter(BaseImporter):
    """Importador de archivos CSV."""
    
    def __init__(self, file_path, table_name, delimiter=',', encoding='utf-8'):
        """
        Inicializar importador CSV.
        
        Args:
            file_path: Ruta del archivo CSV
            table_name: Nombre de la tabla
            delimiter: Delimitador del CSV (por defecto coma)
            encoding: Codificación del archivo
        """
        super().__init__(file_path, table_name)
        self.delimiter = delimiter
        self.encoding = encoding
    
    def read_file(self):
        """Leer archivo CSV."""
        try:
            with open(self.file_path, 'r', encoding=self.encoding) as file:
                reader = csv.DictReader(file, delimiter=self.delimiter)
                self.data = list(reader)
            logger.info(f"CSV leído: {len(self.data)} filas")
            return True
        except Exception as e:
            logger.error(f"Error leyendo CSV: {e}")
            self.add_error(f"Error leyendo archivo: {str(e)}")
            return False
    
    def validate_data(self):
        """Validar datos del CSV."""
        if not self.data:
            self.add_error("No hay datos en el archivo CSV")
            return False
        
        # Validar que todas las filas tengan columnas
        headers = list(self.data[0].keys()) if self.data else []
        
        for i, row in enumerate(self.data):
            if len(row) != len(headers):
                self.add_error(f"Fila {i+1}: número de columnas inconsistente")
        
        return len(self.errors) == 0
