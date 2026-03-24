"""Configuración de la aplicación."""

import json
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
    PBX_DB_NAME = os.getenv("PBX_DB_NAME", "registro_agentes")
    PBX_EXTENSIONS_TABLE = os.getenv("PBX_EXTENSIONS_TABLE", "extensions_pbx")
    
    # Conexión String
    DATABASE_URL = f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    # Servidor
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", 8000))
    SSL_PORT = int(os.getenv("SSL_PORT", 8443))
    API_DEBUG = os.getenv("API_DEBUG", "False").lower() == "true"
    FORCE_HTTPS = os.getenv("FORCE_HTTPS", "True").lower() == "true"
    PUBLIC_BASE_URL = (os.getenv("PUBLIC_BASE_URL", "") or "").strip().rstrip("/")
    LOCAL_HOSTNAME = (os.getenv("LOCAL_HOSTNAME", "") or "").strip()

    # CORS
    _cors_origins_raw = (os.getenv("CORS_ORIGINS", "") or "").strip()

    @staticmethod
    def _parse_cors_origins(raw: str) -> list[str]:
        if not raw:
            return []

        # Accept JSON array or comma-separated values.
        if raw.startswith("["):
            try:
                values = json.loads(raw)
                if isinstance(values, list):
                    return [str(v).strip() for v in values if str(v).strip()]
            except Exception:
                return []

        return [item.strip() for item in raw.split(",") if item.strip()]

    CORS_ORIGINS = _parse_cors_origins.__func__(_cors_origins_raw)
    _cors_methods_raw = (os.getenv("CORS_ALLOW_METHODS", "") or "").strip()
    _cors_headers_raw = (os.getenv("CORS_ALLOW_HEADERS", "") or "").strip()

    @staticmethod
    def _parse_csv_list(raw: str, default: list[str]) -> list[str]:
        values = [item.strip() for item in (raw or "").split(",") if item.strip()]
        return values or list(default)

    CORS_ALLOW_METHODS = _parse_csv_list.__func__(
        _cors_methods_raw,
        ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    )
    CORS_ALLOW_HEADERS = _parse_csv_list.__func__(
        _cors_headers_raw,
        ["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"],
    )
    
    # Seguridad
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
    JWT_SECRET_KEY = (os.getenv("JWT_SECRET_KEY", "") or "").strip() or SECRET_KEY
    _jwt_prev_keys_raw = (os.getenv("JWT_SECRET_KEY_PREVIOUS", "") or "").strip()
    JWT_SECRET_KEY_PREVIOUS = [
        key.strip() for key in _jwt_prev_keys_raw.split(",") if key.strip()
    ]
    QR_TOKEN_TTL_HOURS = int(os.getenv("QR_TOKEN_TTL_HOURS", 720))
    RECEIPT_RETENTION_DAYS = int(os.getenv("RECEIPT_RETENTION_DAYS", 90))
    AUTO_AGENT_DATA_CLEANUP_ON_STARTUP = os.getenv("AUTO_AGENT_DATA_CLEANUP_ON_STARTUP", "true").lower() == "true"
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # Archivos
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "..", "uploads")
    QR_FOLDER = os.path.join(os.path.dirname(__file__), "..", "qr_codes")
    BACKUP_FOLDER = os.path.join(os.path.dirname(__file__), "..", "backups")
    
    @classmethod
    def create_directories(cls):
        """Crear directorios necesarios."""
        os.makedirs(cls.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(cls.QR_FOLDER, exist_ok=True)
        os.makedirs(cls.BACKUP_FOLDER, exist_ok=True)

    @classmethod
    def get_public_base_url(cls, request=None) -> str:
        """Resolver URL pública base para enlaces QR y acceso desde red."""
        if cls.PUBLIC_BASE_URL:
            return cls.PUBLIC_BASE_URL

        if request is not None:
            forwarded_proto = request.headers.get("x-forwarded-proto")
            forwarded_host = request.headers.get("x-forwarded-host")
            if forwarded_proto and forwarded_host:
                return f"{forwarded_proto}://{forwarded_host}".rstrip("/")
            return str(request.base_url).rstrip("/")

        if cls.LOCAL_HOSTNAME:
            return f"http://{cls.LOCAL_HOSTNAME}:{cls.API_PORT}"

        return f"http://localhost:{cls.API_PORT}"


config = Config()
