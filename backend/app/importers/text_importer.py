"""Text and DAT file importer."""

import logging
from .base_importer import BaseImporter

logger = logging.getLogger(__name__)


class TextImporter(BaseImporter):
    """Importador de archivos TXT y DAT."""
    
    def __init__(self, file_path, table_name, delimiter='\t', encoding='utf-8'):
        """
        Inicializar importador TXT/DAT.
        
        Args:
            file_path: Ruta del archivo
            table_name: Nombre de la tabla
            delimiter: Delimitador del archivo
            encoding: Codificación del archivo
        """
        super().__init__(file_path, table_name)
        self.delimiter = delimiter
        self.encoding = encoding
    
    def read_file(self):
        """Leer archivo TXT/DAT."""
        try:
            with open(self.file_path, 'r', encoding=self.encoding) as file:
                lines = file.readlines()
            
            if not lines:
                self.add_error("Archivo vacío")
                return False
            
            # Primera línea como headers
            headers = [h.strip() for h in lines[0].split(self.delimiter)]
            
            self.data = []
            for i, line in enumerate(lines[1:], start=2):
                values = [v.strip() for v in line.split(self.delimiter)]
                if len(values) == len(headers):
                    row = dict(zip(headers, values))
                    self.data.append(row)
                else:
                    self.add_error(f"Fila {i}: número de columnas inconsistente")
            
            logger.info(f"TXT leído: {len(self.data)} filas")
            return True
        except Exception as e:
            logger.error(f"Error leyendo TXT: {e}")
            self.add_error(f"Error leyendo archivo: {str(e)}")
            return False
    
    def validate_data(self):
        """Validar datos del TXT."""
        if not self.data:
            self.add_error("No hay datos en el archivo")
            return False
        
        return len(self.errors) == 0
