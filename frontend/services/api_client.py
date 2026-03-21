"""Cliente HTTP para conectar con la API del backend."""

import requests
import logging

logger = logging.getLogger(__name__)


class APIClient:
    """Cliente para comunicarse con la API del backend."""
    
    def __init__(self, base_url="http://localhost:8000"):
        """
        Inicializar cliente.
        
        Args:
            base_url: URL base del servidor API
        """
        self.base_url = base_url
        self.timeout = 10
    
    def health_check(self):
        """Verificar conexión con el servidor."""
        try:
            response = requests.get(
                f"{self.base_url}/api/health",
                timeout=self.timeout
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error checking health: {e}")
            return False
    
    def import_csv(self, file_path, table_name, delimiter=","):
        """Importar archivo CSV."""
        try:
            with open(file_path, 'rb') as f:
                files = {'file': f}
                data = {'table_name': table_name, 'delimiter': delimiter}
                response = requests.post(
                    f"{self.base_url}/api/import/csv",
                    files=files,
                    data=data,
                    timeout=self.timeout
                )
            return response.json()
        except Exception as e:
            logger.error(f"Error importing CSV: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_data(self, table_name):
        """Obtener datos de una tabla."""
        try:
            response = requests.get(
                f"{self.base_url}/api/data/{table_name}",
                timeout=self.timeout
            )
            return response.json()
        except Exception as e:
            logger.error(f"Error getting data: {e}")
            return {"status": "error", "message": str(e)}
    
    def generate_qr(self, text):
        """Generar código QR."""
        try:
            response = requests.post(
                f"{self.base_url}/api/qr/generate",
                json={"text": text},
                timeout=self.timeout
            )
            return response.json()
        except Exception as e:
            logger.error(f"Error generating QR: {e}")
            return {"status": "error", "message": str(e)}
