"""Endpoints de autenticación."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.orm import get_db
from app.database.repositorios import RepositorioUsuario, RepositorioAuditoria
from app.api.usuarios import _purge_expired_temp_users
from app.schemas import UsuarioCrear, UsuarioAuth, Usuario, Token
from app.security import create_access_token, get_current_user, get_client_ip, ACCESS_TOKEN_EXPIRE_MINUTES, normalize_role
from datetime import timedelta
from fastapi import Request
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["Autenticación"])


@router.post("/registrar", response_model=Usuario)
async def registrar(usuario_in: UsuarioCrear, db: Session = Depends(get_db), request: Request = None):
    """Registrar nuevo usuario."""
    repo_usuario = RepositorioUsuario(db)
    repo_auditoria = RepositorioAuditoria(db)
    
    # Verificar que no existe el usuario
    if repo_usuario.obtener_por_username(usuario_in.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username ya existe"
        )
    
    if repo_usuario.obtener_por_email(usuario_in.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email ya está registrado"
        )
    
    # Registro público: forzar mínimo privilegio y evitar elevación por payload cliente.
    usuario_seguro = usuario_in.model_copy(update={
        "rol": "viewer",
        "es_admin": False,
        "es_activo": True,
    })

    # Crear usuario
    usuario = repo_usuario.crear(usuario_seguro)
    
    # Auditoría
    repo_auditoria.registrar_accion(
        usuario_id=usuario.id,
        tipo_accion="REGISTER",
        tabla="usuarios",
        registro_id=usuario.id,
        descripcion=f"Usuario registrado: {usuario.username}",
        resultado="SUCCESS",
        ip_origen=get_client_ip(request) if request else None
    )
    
    return usuario


@router.post("/login", response_model=Token)
async def login(credenciales: UsuarioAuth, db: Session = Depends(get_db), request: Request = None):
    """Login de usuario."""
    repo_usuario = RepositorioUsuario(db)
    repo_auditoria = RepositorioAuditoria(db)

    _purge_expired_temp_users(db)
    
    usuario = repo_usuario.autenticar(credenciales.username, credenciales.password)
    
    if not usuario:
        # Auditoría de intento fallido
        repo_auditoria.registrar_accion(
            usuario_id=None,
            tipo_accion="LOGIN",
            tabla="usuarios",
            descripcion=f"Intento de login fallido: {credenciales.username}",
            resultado="FAILED",
            ip_origen=get_client_ip(request) if request else None
        )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña inválidos"
        )
    
    if not usuario.es_activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inactivo"
        )
    
    # Crear token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": usuario.username,
            "id": usuario.id,
            "es_admin": usuario.es_admin,
            "rol": normalize_role(usuario.rol, usuario.es_admin),
        },
        expires_delta=access_token_expires
    )
    
    # Actualizar última sesión
    repo_usuario.actualizar_ultima_sesion(usuario.id)
    
    # Auditoría
    repo_auditoria.registrar_accion(
        usuario_id=usuario.id,
        tipo_accion="LOGIN",
        tabla="usuarios",
        descripcion=f"Login exitoso: {usuario.username}",
        resultado="SUCCESS",
        ip_origen=get_client_ip(request) if request else None
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "usuario": usuario
    }


@router.get("/me", response_model=Usuario)
async def me(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Obtener usuario actual."""
    repo_usuario = RepositorioUsuario(db)
    _purge_expired_temp_users(db, actor_user_id=current_user.get("id"))
    usuario = repo_usuario.obtener_por_username(current_user["username"])
    
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    return usuario
