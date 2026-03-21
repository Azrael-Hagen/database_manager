"""Configuración de la aplicación."""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuración base de la aplicación."""
    
    # Base de Datos
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "database_manager")
    DB_PORT = int(os.getenv("DB_PORT", 3306))
    
    # Conexión String
    DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    # Servidor
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", 8000))
    API_DEBUG = os.getenv("API_DEBUG", "True").lower() == "true"
    
    # Seguridad
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # Archivos
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "..", "uploads")
    QR_FOLDER = os.path.join(os.path.dirname(__file__), "..", "qr_codes")
    
    @classmethod
    def create_directories(cls):
        """Crear directorios necesarios."""
        os.makedirs(cls.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(cls.QR_FOLDER, exist_ok=True)


config = Config()
