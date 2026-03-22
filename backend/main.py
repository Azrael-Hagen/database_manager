"""Aplicación FastAPI principal - Producción."""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import logging
import os
from datetime import datetime
import signal
import sys

from app.config import config
from app.database.orm import init_db, get_db, SessionLocal
from app.api.auth import router as auth_router
from app.api.datos import router as datos_router
from app.api.importacion import router as importacion_router
from app.api.database import router as database_router
from app.api.usuarios import router as usuarios_router
from app.api.auditoria import router as auditoria_router
from app.api.qr import router as qr_router
from app.utils.pagos import generar_alertas_miercoles_pendientes
from app.utils.backups import create_weekly_backup

# Configurar logging
logging.basicConfig(
    level=config.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Crear directorios necesarios
config.create_directories()
os.makedirs('logs', exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Eventos de inicio y apagado usando lifespan (reemplaza on_event)."""
    logger.info("=" * 60)
    logger.info("Iniciando Database Manager API - PRODUCCION")
    logger.info(f"Ambiente: {'DEBUG' if config.API_DEBUG else 'PRODUCCION'}")
    logger.info(f"BD: {config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}")
    logger.info(f"Servidor: {config.API_HOST}:{config.API_PORT}")
    logger.info("=" * 60)

    try:
        init_db()
        logger.info("Base de datos inicializada correctamente")

        db = SessionLocal()
        try:
            resumen_alertas = generar_alertas_miercoles_pendientes(db)
            logger.info(f"Corte semanal de cobro ejecutado: {resumen_alertas}")

            resumen_backup = create_weekly_backup(db)
            logger.info(f"Respaldo semanal: {resumen_backup}")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error inicializando BD: {e}")
        raise

    try:
        yield
    finally:
        logger.info("Apagando Database Manager API")


# Crear aplicación FastAPI
app = FastAPI(
    title="Database Manager API",
    description="API profesional para gestionar base de datos con importación de archivos, QR, autenticación y auditoría",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# MIDDLEWARE

# CORS - Configurar según ambiente
cors_origins = config.CORS_ORIGINS or [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
]

if not config.API_DEBUG and not config.CORS_ORIGINS:
    cors_origins = [
        "https://yourdomain.com",
        "https://www.yourdomain.com",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MANEJADORES DE ERRORES

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Manejar errores de validación."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "error",
            "mensaje": "Validación fallida",
            "detalles": str(exc.errors())
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Manejar excepciones generales."""
    logger.error(f"Error no manejado: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "mensaje": "Error interno del servidor",
            "detalles": str(exc) if config.API_DEBUG else None
        },
    )


# ROUTERS

# Incluir routers de API
app.include_router(auth_router)
app.include_router(datos_router)
app.include_router(importacion_router)
app.include_router(database_router)
app.include_router(usuarios_router)
app.include_router(auditoria_router)
app.include_router(qr_router)


# HEALTH CHECK

@app.get("/api/health", tags=["Sistema"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }


# SERVIR ARCHIVOS ESTÁTICOS

web_path = os.path.join(os.path.dirname(__file__), "..", "web")
if os.path.exists(web_path):
    app.mount("/", StaticFiles(directory=web_path, html=True), name="web")


if __name__ == "__main__":
    import uvicorn
    
    def signal_handler(sig, frame):
        logger.info("Recibida señal de interrupción (Ctrl+C). Cerrando servidor...")
        sys.exit(0)
    
    # Registrar manejador de señales
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info(f"Iniciando servidor en {config.API_HOST}:{config.API_PORT}")
    logger.info("Presiona Ctrl+C para detener el servidor")
    
    try:
        uvicorn.run(
            "main:app",
            host=config.API_HOST,
            port=config.API_PORT,
            reload=False,
            log_level=config.LOG_LEVEL.lower()
        )
    except KeyboardInterrupt:
        logger.info("Servidor detenido por el usuario")
    except Exception as e:
        logger.error(f"Error al iniciar servidor: {e}")
        sys.exit(1)
