"""Endpoints para gestión de usuarios."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database.orm import get_db
from app.database.repositorios import RepositorioUsuario, RepositorioAuditoria
from app.schemas import Usuario, UsuarioCrear, UsuarioActualizar, PasswordUpdate
from app.security import get_current_user, hash_password
from app.models import Usuario as UsuarioModel
import logging
import json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/usuarios", tags=["User Management"])


@router.get("/", response_model=list[Usuario])
async def listar_usuarios(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Listar todos los usuarios."""
    # Solo admin puede ver todos los usuarios
    if not current_user.get('es_admin', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para ver usuarios"
        )

    repo = RepositorioUsuario(db)
    usuarios = repo.obtener_todos(skip=skip, limit=limit)
    logger.info(f"Usuario {current_user['username']} listó {len(usuarios)} usuarios")
    return usuarios


@router.get("/{user_id}", response_model=Usuario)
async def obtener_usuario(
    user_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener usuario por ID."""
    # Solo admin o el propio usuario
    if not current_user.get('es_admin', False) and current_user['id'] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para ver este usuario"
        )

    repo = RepositorioUsuario(db)
    usuario = repo.obtener_por_id(user_id)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    return usuario


@router.post("/", response_model=Usuario)
async def crear_usuario(
    usuario_in: UsuarioCrear,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Crear nuevo usuario (solo admin)."""
    if not current_user.get('es_admin', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores pueden crear usuarios"
        )

    repo = RepositorioUsuario(db)
    repo_auditoria = RepositorioAuditoria(db)

    # Verificar si el usuario ya existe
    if repo.obtener_por_username(usuario_in.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El nombre de usuario ya existe"
        )

    if repo.obtener_por_email(usuario_in.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya está registrado"
        )

    # Crear usuario
    usuario_dict = usuario_in.dict()
    usuario_dict['hashed_password'] = hash_password(usuario_in.password)
    usuario_dict.pop('password')  # Remover password del dict

    usuario = repo.crear_usuario(usuario_dict)

    # Auditoría
    repo_auditoria.registrar_accion(
        usuario_id=current_user['id'],
        tipo_accion="CREAR",
        tabla="usuarios",
        registro_id=usuario.id,
        descripcion=f"Usuario creado: {usuario.username}",
        datos_nuevos=json.dumps({"username": usuario.username, "email": usuario.email}),
        resultado="SUCCESS"
    )

    logger.info(f"Usuario {current_user['username']} creó usuario: {usuario.username}")
    return usuario


@router.put("/{user_id}", response_model=Usuario)
async def actualizar_usuario(
    user_id: int,
    usuario_in: UsuarioActualizar,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Actualizar usuario."""
    # Solo admin o el propio usuario
    if not current_user.get('es_admin', False) and current_user['id'] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para actualizar este usuario"
        )

    repo = RepositorioUsuario(db)
    repo_auditoria = RepositorioAuditoria(db)

    usuario = repo.obtener_por_id(user_id)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )

    # Datos anteriores para auditoría
    datos_anteriores = {
        "username": usuario.username,
        "email": usuario.email,
        "nombre_completo": usuario.nombre_completo,
        "es_admin": usuario.es_admin,
        "es_activo": usuario.es_activo
    }

    # Si no es admin, no puede cambiar permisos
    if not current_user.get('es_admin', False):
        usuario_in.es_admin = usuario.es_admin  # Mantener valor actual

    usuario_actualizado = repo.actualizar_usuario(user_id, usuario_in.dict(exclude_unset=True))

    # Auditoría
    repo_auditoria.registrar_accion(
        usuario_id=current_user['id'],
        tipo_accion="ACTUALIZAR",
        tabla="usuarios",
        registro_id=user_id,
        descripcion=f"Usuario actualizado: {usuario.username}",
        datos_anteriores=json.dumps(datos_anteriores),
        datos_nuevos=json.dumps(usuario_in.dict(exclude_unset=True)),
        resultado="SUCCESS"
    )

    logger.info(f"Usuario {current_user['username']} actualizó usuario: {usuario.username}")
    return usuario_actualizado


@router.delete("/{user_id}")
async def eliminar_usuario(
    user_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Eliminar usuario (soft delete, solo admin)."""
    if not current_user.get('es_admin', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores pueden eliminar usuarios"
        )

    if current_user['id'] == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes eliminarte a ti mismo"
        )

    repo = RepositorioUsuario(db)
    repo_auditoria = RepositorioAuditoria(db)

    usuario = repo.obtener_por_id(user_id)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )

    repo.eliminar_usuario(user_id)

    # Auditoría
    repo_auditoria.registrar_accion(
        usuario_id=current_user['id'],
        tipo_accion="ELIMINAR",
        tabla="usuarios",
        registro_id=user_id,
        descripcion=f"Usuario eliminado: {usuario.username}",
        resultado="SUCCESS"
    )

    logger.info(f"Usuario {current_user['username']} eliminó usuario: {usuario.username}")
    return {"status": "success", "mensaje": "Usuario eliminado"}


@router.put("/{user_id}/password")
async def cambiar_password(
    user_id: int,
    password_data: PasswordUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cambiar contraseña de usuario."""
    # Solo admin o el propio usuario
    if not current_user.get('es_admin', False) and current_user['id'] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para cambiar esta contraseña"
        )

    repo = RepositorioUsuario(db)
    repo_auditoria = RepositorioAuditoria(db)

    usuario = repo.obtener_por_id(user_id)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )

    nueva_password_hash = hash_password(password_data.password)
    repo.actualizar_password(user_id, nueva_password_hash)

    # Auditoría
    repo_auditoria.registrar_accion(
        usuario_id=current_user['id'],
        tipo_accion="ACTUALIZAR",
        tabla="usuarios",
        registro_id=user_id,
        descripcion=f"Contraseña cambiada: {usuario.username}",
        resultado="SUCCESS"
    )

    logger.info(f"Usuario {current_user['username']} cambió contraseña de: {usuario.username}")
    return {"status": "success", "mensaje": "Contraseña actualizada"}