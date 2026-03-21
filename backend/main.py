"""Aplicación FastAPI principal - Producción."""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging
import os
from datetime import datetime

from app.config import config
from app.database.orm import init_db, get_db
from app.api.auth import router as auth_router
from app.api.datos import router as datos_router
from app.api.importacion import router as importacion_router

# Configurar logging
logging.basicConfig(
    level=config.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Crear directorios necesarios
config.create_directories()
os.makedirs('logs', exist_ok=True)

# Crear aplicación FastAPI
app = FastAPI(
    title="Database Manager API",
    description="API profesional para gestionar base de datos con importación de archivos, QR, autenticación y auditoría",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# MIDDLEWARE

# CORS - Configurar según ambiente
cors_origins = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
]

if not config.API_DEBUG:
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


# EVENTOS DEL CICLO DE VIDA

@app.on_event("startup")
async def startup():
    """Eventos al iniciar la aplicación."""
    logger.info("=" * 60)
    logger.info("Iniciando Database Manager API - PRODUCCIÓN")
    logger.info(f"Ambiente: {'DEBUG' if config.API_DEBUG else 'PRODUCCIÓN'}")
    logger.info(f"BD: {config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}")
    logger.info(f"Servidor: {config.API_HOST}:{config.API_PORT}")
    logger.info("=" * 60)
    
    # Inicializar base de datos
    try:
        init_db()
        logger.info("Base de datos inicializada correctamente")
    except Exception as e:
        logger.error(f"Error inicializando BD: {e}")
        raise


@app.on_event("shutdown")
async def shutdown():
    """Eventos al apagar la aplicación."""
    logger.info("Apagando Database Manager API")


if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Iniciando servidor en {config.API_HOST}:{config.API_PORT}")
    uvicorn.run(
        "main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=config.API_DEBUG,
        log_level=config.LOG_LEVEL.lower()
    )
