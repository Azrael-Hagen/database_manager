"""Utilidades de seguridad y autenticación."""

from datetime import datetime, timedelta, timezone
from functools import lru_cache
import ipaddress
import socket
import jwt
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.config import config
from app.database.orm import get_db
from app.models import Usuario
import logging

logger = logging.getLogger(__name__)

# Configuración de encriptación
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Configuración JWT
JWT_SIGNING_KEY = str(config.JWT_SECRET_KEY or "").strip()
JWT_PREVIOUS_KEYS = [str(key).strip() for key in config.JWT_SECRET_KEY_PREVIOUS if str(key).strip()]
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

if not JWT_SIGNING_KEY:
    logger.warning("JWT_SIGNING_KEY vacío; utilizando fallback inseguro temporal")
    JWT_SIGNING_KEY = "change-me-in-production"

security = HTTPBearer()

ROLE_VIEWER = "viewer"
ROLE_CAPTURE = "capture"
ROLE_ADMIN = "admin"
ROLE_SUPER_ADMIN = "super_admin"

_VALID_ROLES = {ROLE_VIEWER, ROLE_CAPTURE, ROLE_ADMIN, ROLE_SUPER_ADMIN}


def normalize_role(role: str | None, es_admin: bool = False) -> str:
    """Normalizar rol y mantener compatibilidad con es_admin legacy."""
    value = str(role or "").strip().lower()
    # super_admin se respeta directamente sin override por es_admin
    if value == ROLE_SUPER_ADMIN:
        return ROLE_SUPER_ADMIN
    if value not in _VALID_ROLES:
        value = ROLE_ADMIN if es_admin else ROLE_VIEWER
    if es_admin and value not in {ROLE_ADMIN, ROLE_SUPER_ADMIN}:
        return ROLE_ADMIN
    return value


def role_rank(role: str | None) -> int:
    value = normalize_role(role)
    return {
        ROLE_VIEWER: 1,
        ROLE_CAPTURE: 2,
        ROLE_ADMIN: 3,
        ROLE_SUPER_ADMIN: 4,
    }.get(value, 1)


def has_minimum_role(current_user: dict, required_role: str) -> bool:
    current_role = normalize_role(current_user.get("rol"), bool(current_user.get("es_admin")))
    return role_rank(current_role) >= role_rank(required_role)


def require_minimum_role(current_user: dict, required_role: str, detail: str):
    if not has_minimum_role(current_user, required_role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def require_capture_role(current_user: dict, detail: str = "No tienes permisos para realizar altas"):
    require_minimum_role(current_user, ROLE_CAPTURE, detail)


def require_admin_role(current_user: dict, detail: str = "Solo administradores pueden realizar esta acción"):
    require_minimum_role(current_user, ROLE_ADMIN, detail)


def require_super_admin_role(current_user: dict, detail: str = "Solo el super administrador puede realizar esta acción"):
    require_minimum_role(current_user, ROLE_SUPER_ADMIN, detail)


def is_super_admin(current_user: dict) -> bool:
    role = normalize_role(current_user.get("rol"), bool(current_user.get("es_admin")))
    return role == ROLE_SUPER_ADMIN


def hash_password(password: str) -> str:
    """Hashear contraseña."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verificar contraseña."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """Crear token JWT."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SIGNING_KEY, algorithm=ALGORITHM)
    
    return encoded_jwt


def verify_token(token: str) -> dict:
    """Verificar y decodificar token JWT."""
    verification_keys = [JWT_SIGNING_KEY, *JWT_PREVIOUS_KEYS]

    for key in verification_keys:
        try:
            payload = jwt.decode(token, key, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token inválido"
                )
            role = normalize_role(payload.get("rol"), bool(payload.get("es_admin", False)))
            return {
                "username": username,
                "id": payload.get("id"),
                "es_admin": role in {ROLE_ADMIN, ROLE_SUPER_ADMIN},
                "rol": role,
                "es_super_admin": role == ROLE_SUPER_ADMIN,
                "email": payload.get("email")
            }
        except InvalidTokenError:
            continue

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido o expirado"
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """Dependency para obtener usuario actual del token y validar estado real en BD."""
    token = credentials.credentials
    token_user = verify_token(token)

    db_user = db.query(Usuario).filter(Usuario.username == token_user["username"]).first()
    if not db_user:
        logger.warning("Token valido para usuario no existente en BD: %s", token_user["username"])
        return token_user

    if not bool(db_user.es_activo):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inactivo"
        )

    canonical_role = normalize_role(db_user.rol, bool(db_user.es_admin))
    token_user.update(
        {
            "id": db_user.id,
            "email": db_user.email,
            "rol": canonical_role,
            "es_admin": canonical_role in {ROLE_ADMIN, ROLE_SUPER_ADMIN},
            "es_super_admin": canonical_role == ROLE_SUPER_ADMIN,
        }
    )
    return token_user


def get_client_ip(request: Request) -> str:
    """Obtener IP del cliente."""
    if request.client:
        return request.client.host
    return "unknown"


@lru_cache(maxsize=1)
def _server_machine_addresses() -> set[str]:
    """Resolver direcciones IP locales válidas para la máquina servidor."""
    addresses = {"127.0.0.1", "::1", "localhost"}
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None):
            ip = info[4][0]
            addresses.add(ip)
    except Exception:
        # En caso de fallo DNS local, mantenemos solo loopback.
        pass
    return addresses


def is_server_machine_request(request: Request) -> bool:
    """Validar que la petición viene desde la máquina donde corre el backend."""
    client_ip = get_client_ip(request)
    if client_ip in _server_machine_addresses():
        return True
    try:
        parsed = ipaddress.ip_address(client_ip)
        return parsed.is_loopback
    except ValueError:
        return False


def require_server_machine_request(
    request: Request,
    detail: str = "Esta acción de depuración solo se permite desde la máquina servidor"
):
    """Restringir acciones de depuración a ejecución local en el servidor."""
    if not is_server_machine_request(request):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
