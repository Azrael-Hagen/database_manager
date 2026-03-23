"""Aplicación FastAPI principal - Producción."""

from fastapi import FastAPI, Request, status, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import logging
import os
from datetime import datetime
import socket
import ipaddress
import signal
import sys
import json
import multiprocessing
from pathlib import Path

from app.config import config
from app.database.orm import init_db, get_db, SessionLocal
from app.api.auth import router as auth_router
from app.api.datos import router as datos_router
from app.api.importacion import router as importacion_router
from app.api.database import router as database_router
from app.api.usuarios import router as usuarios_router
from app.api.auditoria import router as auditoria_router
from app.api.qr import router as qr_router
from app.api.export import router as export_router
from app.api.dashboard import router as dashboard_router
from app.security import get_current_user
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

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"
SOURCES_DIR = WEB_DIR / "sources"
BRANDING_FILE = SOURCES_DIR / "branding.json"
ALLOWED_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
SSL_CERT_PATH = Path(__file__).parent.parent / "ssl" / "cert.pem"
SSL_KEY_PATH = Path(__file__).parent.parent / "ssl" / "key.pem"


class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        lower_path = str(path).lower()
        if lower_path in {"", "/", "index.html"} or lower_path.endswith((".html", ".js", ".css", ".json")):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

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


def _request_is_https(request: Request) -> bool:
    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    if forwarded_proto == "https":
        return True
    return (request.url.scheme or "").lower() == "https"


def _build_https_redirect_url(request: Request) -> str:
    forwarded_host = (request.headers.get("x-forwarded-host") or "").split(",")[0].strip()
    host_header = (request.headers.get("host") or "").strip()
    raw_host = forwarded_host or host_header or (request.url.hostname or "localhost")

    host_only = raw_host.split(":")[0]
    https_port = int(config.SSL_PORT or 443)
    if https_port == 443:
        authority = host_only
    else:
        authority = f"{host_only}:{https_port}"

    query = f"?{request.url.query}" if request.url.query else ""
    return f"https://{authority}{request.url.path}{query}"


@app.middleware("http")
async def enforce_https_middleware(request: Request, call_next):
    """Forzar HTTPS: redirige HTTP y bloquea si no hay TLS configurado."""
    if not config.FORCE_HTTPS:
        response = await call_next(request)
        return response

    if request.url.path == "/api/health":
        return await call_next(request)

    if _request_is_https(request):
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    tls_ready = SSL_CERT_PATH.exists() and SSL_KEY_PATH.exists()
    if tls_ready:
        return RedirectResponse(url=_build_https_redirect_url(request), status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    return JSONResponse(
        status_code=status.HTTP_426_UPGRADE_REQUIRED,
        content={
            "status": "error",
            "mensaje": "HTTPS requerido. Configura TLS antes de ingresar.",
            "detalle": "Ejecuta scripts/setup-https.ps1 y accede por https.",
        },
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
app.include_router(export_router)
app.include_router(dashboard_router)


# HEALTH CHECK

@app.get("/api/health", tags=["Sistema"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }


def _is_private_ipv4(ip: str) -> bool:
    try:
        parsed = ipaddress.ip_address(ip)
        return parsed.version == 4 and parsed.is_private and not parsed.is_loopback
    except ValueError:
        return False


def _collect_local_ipv4_candidates() -> list[str]:
    candidates: list[str] = []
    sock = None

    # Primary route-based IP detection (does not send external traffic).
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        if ip:
            candidates.append(ip)
    except Exception:
        pass
    finally:
        try:
            if sock:
                sock.close()
        except Exception:
            pass

    try:
        host_ips = socket.gethostbyname_ex(socket.gethostname())[2]
        candidates.extend(host_ips)
    except Exception:
        pass

    unique: list[str] = []
    for ip in candidates:
        if ip and ip not in unique:
            unique.append(ip)
    return unique


def _is_local_request_host(host: str | None) -> bool:
    if not host:
        return False
    host_value = str(host).strip().lower()
    local_names = {"127.0.0.1", "::1", "localhost", socket.gethostname().lower()}
    if host_value in local_names:
        return True
    return host_value in {ip.lower() for ip in _collect_local_ipv4_candidates()}


def _read_branding_config() -> dict:
    default = {
        "appName": "Phantom Database",
        "subtitle": "server console",
        "logoPath": "sources/Logo%20Phantom%20Databas.png",
    }
    try:
        if BRANDING_FILE.exists():
            with BRANDING_FILE.open("r", encoding="utf-8") as fh:
                payload = json.load(fh)
                if isinstance(payload, dict):
                    default.update(payload)
    except Exception as exc:
        logger.warning(f"No se pudo leer branding.json: {exc}")
    return default


def _write_branding_config(payload: dict) -> None:
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    with BRANDING_FILE.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def _ensure_local_admin(request: Request, current_user: dict) -> None:
    if not current_user.get("es_admin", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo administradores pueden cambiar el logo")
    client_host = request.client.host if request.client else None
    if not _is_local_request_host(client_host):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="El cambio de logo solo está permitido desde el servidor local")


@app.get("/api/network/local", tags=["Sistema"])
async def local_network_info(request: Request):
    """Devuelve IP local sugerida y URL para compartir en LAN."""
    candidates = _collect_local_ipv4_candidates()
    preferred = next((ip for ip in candidates if _is_private_ipv4(ip)), None)
    ip_local = preferred or next((ip for ip in candidates if ip != "127.0.0.1"), None) or "127.0.0.1"

    port = request.url.port or config.API_PORT or 8000
    scheme = request.url.scheme or "http"
    default_port = 443 if scheme == "https" else 80
    share_url = f"{scheme}://{ip_local}:{port}"
    share_url_no_port = f"{scheme}://{ip_local}"
    share_url_preferida = share_url_no_port if int(port) == int(default_port) else share_url

    return {
        "status": "ok",
        "ip_local": ip_local,
        "puerto": int(port),
        "share_url": share_url,
        "share_url_no_port": share_url_no_port,
        "share_url_preferida": share_url_preferida,
        "usa_puerto_por_defecto": bool(int(port) == int(default_port)),
        "hostname": socket.gethostname(),
    }


@app.get("/api/branding/admin-status", tags=["Sistema"])
async def branding_admin_status(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    branding = _read_branding_config()
    client_host = request.client.host if request.client else None
    return {
        "status": "ok",
        "branding": branding,
        "can_manage_logo": bool(current_user.get("es_admin", False) and _is_local_request_host(client_host)),
        "client_host": client_host,
    }


@app.post("/api/branding/logo", tags=["Sistema"])
async def upload_branding_logo(
    request: Request,
    logo: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    _ensure_local_admin(request, current_user)

    extension = Path(logo.filename or "").suffix.lower()
    if extension not in ALLOWED_LOGO_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Formato no permitido. Usa PNG, JPG, WEBP, GIF o SVG")

    raw = await logo.read()
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo está vacío")
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo supera el límite de 5 MB")

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    safe_name = f"custom-logo-{timestamp}{extension}"
    target_file = SOURCES_DIR / safe_name
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    target_file.write_bytes(raw)

    branding = _read_branding_config()
    branding["logoPath"] = f"sources/{safe_name}"
    _write_branding_config(branding)

    return {
        "status": "ok",
        "mensaje": "Logo actualizado correctamente",
        "branding": branding,
    }


@app.get("/")
async def serve_index():
    index_file = WEB_DIR / "index.html"
    response = FileResponse(index_file)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


# SERVIR ARCHIVOS ESTÁTICOS

web_path = os.path.join(os.path.dirname(__file__), "..", "web")
if os.path.exists(web_path):
    app.mount("/", NoCacheStaticFiles(directory=web_path, html=True), name="web")


# ── Servidor HTTPS auxiliar (arrancado desde __main__) ──────────────────────

def _run_https_server(host: str, port: int, ssl_certfile: str, ssl_keyfile: str, log_level: str) -> None:
    """Proceso independiente que sirve HTTPS con los certificados TLS."""
    import uvicorn  # import local para que funcione el spawn en Windows
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        ssl_certfile=ssl_certfile,
        ssl_keyfile=ssl_keyfile,
        reload=False,
        log_level=log_level,
    )


if __name__ == "__main__":
    # Windows multiprocessing requiere este guard
    multiprocessing.freeze_support()

    import uvicorn

    def signal_handler(sig, frame):
        logger.info("Recibida señal de interrupción (Ctrl+C). Cerrando servidor...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Detectar certificados TLS
    ssl_dir  = Path(__file__).parent.parent / "ssl"
    ssl_cert = ssl_dir / "cert.pem"
    ssl_key  = ssl_dir / "key.pem"
    ssl_port = int(os.getenv("SSL_PORT", 8443))

    https_proc = None
    if ssl_cert.exists() and ssl_key.exists():
        logger.info(f"Certificados TLS encontrados en {ssl_dir}")
        logger.info(f"Iniciando servidor HTTPS en {config.API_HOST}:{ssl_port}")
        https_proc = multiprocessing.Process(
            target=_run_https_server,
            args=(config.API_HOST, ssl_port, str(ssl_cert), str(ssl_key), config.LOG_LEVEL.lower()),
            daemon=True,
            name="https-server",
        )
        https_proc.start()
    else:
        logger.info("Sin certificados TLS — solo HTTP activo.")
        logger.info("Para HTTPS ejecuta:  scripts\\setup-https.ps1")

    logger.info(f"Iniciando servidor HTTP en {config.API_HOST}:{config.API_PORT}")
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
    finally:
        if https_proc and https_proc.is_alive():
            https_proc.terminate()
            https_proc.join(timeout=5)
