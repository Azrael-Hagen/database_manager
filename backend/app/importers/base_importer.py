"""Base importer class."""

from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class BaseImporter(ABC):
    """Clase base para importadores de datos."""
    
    def __init__(self, file_path, table_name):
        """
        Inicializar importador.
        
        Args:
            file_path: Ruta del archivo a importar
            table_name: Nombre de la tabla donde insertar
        """
        self.file_path = file_path
        self.table_name = table_name
        self.data = []
        self.errors = []
    
    @abstractmethod
    def read_file(self):
        """Leer el archivo y cargar datos."""
        pass
    
    @abstractmethod
    def validate_data(self):
        """Validar los datos antes de importar."""
        pass
    
    def get_data(self):
        """Obtener los datos leídos."""
        return self.data
    
    def get_errors(self):
        """Obtener errores de validación."""
        return self.errors
    
    def add_error(self, error_message):
        """Agregar error a la lista."""
        self.errors.append(error_message)
        logger.warning(f"Error de validación: {error_message}")
    
    def clear_data(self):
        """Limpiar datos cargados."""
        self.data = []
        self.errors = []
