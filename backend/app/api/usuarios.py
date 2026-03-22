"""Endpoints para gestión de usuarios."""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body, Request
from sqlalchemy.orm import Session
from app.database.orm import get_db
from app.database.repositorios import RepositorioUsuario, RepositorioAuditoria
from app.schemas import Usuario, UsuarioCrear, UsuarioActualizar, PasswordUpdate
from app.security import normalize_role, get_current_user, hash_password, require_admin_role, require_server_machine_request
from app.models import Usuario as UsuarioModel
import logging
import json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/usuarios", tags=["User Management"])

TEMP_USER_PREFIXES = ("tmp_", "temp_", "test_", "demo_")


@router.get("/", response_model=list[Usuario])
async def listar_usuarios(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    ordenar_por: str = Query("fecha_creacion"),
    direccion: str = Query("desc"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Listar todos los usuarios."""
    require_admin_role(current_user, "No tienes permisos para ver usuarios")

    repo = RepositorioUsuario(db)
    allowed_fields = {
        "id": UsuarioModel.id,
        "username": UsuarioModel.username,
        "email": UsuarioModel.email,
        "nombre_completo": UsuarioModel.nombre_completo,
        "rol": UsuarioModel.rol,
        "es_activo": UsuarioModel.es_activo,
        "fecha_creacion": UsuarioModel.fecha_creacion,
        "fecha_ultima_sesion": UsuarioModel.fecha_ultima_sesion,
    }
    order_field = allowed_fields.get((ordenar_por or "").strip(), UsuarioModel.fecha_creacion)
    direction_value = (direccion or "desc").strip().lower()
    order_clause = order_field.desc() if direction_value != "asc" else order_field.asc()
    usuarios = db.query(UsuarioModel).order_by(order_clause, UsuarioModel.id.desc()).offset(skip).limit(limit).all()
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
    require_admin_role(current_user, "Solo administradores pueden crear usuarios")

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
        usuario_in.es_admin = usuario.es_admin
        usuario_in.rol = normalize_role(usuario.rol, usuario.es_admin)

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
    hard_delete: bool = Query(False),
    reassign_imports_to: int | None = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Eliminar usuario (soft delete o definitivo, solo admin)."""
    require_admin_role(current_user, "Solo administradores pueden eliminar usuarios")

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

    if hard_delete:
        try:
            repo.eliminar_usuario_definitivo(user_id, reassigned_user_id=reassign_imports_to or current_user['id'])
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    else:
        repo.eliminar_usuario(user_id)

    # Auditoría
    repo_auditoria.registrar_accion(
        usuario_id=current_user['id'],
        tipo_accion="ELIMINAR",
        tabla="usuarios",
        registro_id=user_id,
        descripcion=f"Usuario {'eliminado definitivamente' if hard_delete else 'eliminado'}: {usuario.username}",
        resultado="SUCCESS"
    )

    logger.info(f"Usuario {current_user['username']} eliminó usuario: {usuario.username}")
    return {"status": "success", "mensaje": "Usuario eliminado definitivamente" if hard_delete else "Usuario eliminado"}


@router.get("/maintenance/overview")
async def resumen_mantenimiento_usuarios(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mostrar candidatos para depuración y reclasificación de usuarios."""
    require_admin_role(current_user, "Solo administradores pueden depurar usuarios")

    now = datetime.utcnow()
    stale_cutoff = now - timedelta(days=60)
    users = db.query(UsuarioModel).order_by(UsuarioModel.fecha_creacion.desc()).all()

    candidates = []
    for user in users:
        username = (user.username or "").lower()
        is_temp_name = username.startswith(TEMP_USER_PREFIXES)
        stale_session = user.fecha_ultima_sesion is None or user.fecha_ultima_sesion < stale_cutoff
        inactive = not bool(user.es_activo)
        if is_temp_name or (inactive and stale_session):
            candidates.append(
                {
                    "id": user.id,
                    "username": user.username,
                    "rol": normalize_role(user.rol, user.es_admin),
                    "es_activo": bool(user.es_activo),
                    "fecha_creacion": user.fecha_creacion.isoformat() if user.fecha_creacion else None,
                    "fecha_ultima_sesion": user.fecha_ultima_sesion.isoformat() if user.fecha_ultima_sesion else None,
                    "is_temp_name": is_temp_name,
                    "is_stale": stale_session,
                }
            )

    return {
        "status": "success",
        "summary": {
            "total": len(users),
            "activos": sum(1 for u in users if u.es_activo),
            "inactivos": sum(1 for u in users if not u.es_activo),
            "viewers": sum(1 for u in users if normalize_role(u.rol, u.es_admin) == "viewer"),
            "captures": sum(1 for u in users if normalize_role(u.rol, u.es_admin) == "capture"),
            "admins": sum(1 for u in users if normalize_role(u.rol, u.es_admin) == "admin"),
            "candidatos_depurar": len(candidates),
        },
        "candidates": candidates,
    }


@router.post("/maintenance/reclassify")
async def reclasificar_usuarios(
    payload: dict = Body(...),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reclasificar usuarios en lote (rol + activo)."""
    require_admin_role(current_user, "Solo administradores pueden reclasificar usuarios")
    updates = (payload or {}).get("updates") or []
    if not isinstance(updates, list) or not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debes enviar updates con al menos un usuario")

    repo = RepositorioUsuario(db)
    repo_auditoria = RepositorioAuditoria(db)
    updated = []
    for item in updates:
        try:
            user_id = int(item.get("id"))
        except Exception:
            continue
        if user_id == current_user["id"]:
            continue
        usuario = repo.obtener_por_id(user_id)
        if not usuario:
            continue
        changes = {}
        if "rol" in item and item.get("rol") is not None:
            changes["rol"] = normalize_role(item.get("rol"), bool(item.get("rol") == "admin"))
        if "es_activo" in item and item.get("es_activo") is not None:
            changes["es_activo"] = bool(item.get("es_activo"))
        if not changes:
            continue
        repo.actualizar_usuario(user_id, changes)
        updated.append({"id": user_id, **changes})

    repo_auditoria.registrar_accion(
        usuario_id=current_user['id'],
        tipo_accion="ACTUALIZAR",
        tabla="usuarios",
        descripcion=f"Reclasificación masiva de usuarios: {len(updated)} cambios",
        datos_nuevos=json.dumps(updated, ensure_ascii=False),
        resultado="SUCCESS"
    )
    return {"status": "success", "updated": updated, "count": len(updated)}


@router.post("/maintenance/purge-temporary")
async def purgar_usuarios_temporales(
    request: Request,
    include_inactive_stale: bool = Query(True),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Eliminar definitivamente usuarios temporales y opcionalmente inactivos obsoletos."""
    require_admin_role(current_user, "Solo administradores pueden depurar usuarios")
    require_server_machine_request(request)
    repo = RepositorioUsuario(db)
    repo_auditoria = RepositorioAuditoria(db)

    stale_cutoff = datetime.utcnow() - timedelta(days=60)
    users = db.query(UsuarioModel).all()
    purged = []
    for user in users:
        if user.id == current_user['id']:
            continue
        role = normalize_role(user.rol, user.es_admin)
        username_lower = (user.username or "").lower()
        is_temp = username_lower.startswith(TEMP_USER_PREFIXES)
        is_stale_inactive = include_inactive_stale and (not user.es_activo) and (
            user.fecha_ultima_sesion is None or user.fecha_ultima_sesion < stale_cutoff
        )
        if role == "admin":
            continue
        if not is_temp and not is_stale_inactive:
            continue
        try:
            repo.eliminar_usuario_definitivo(user.id, reassigned_user_id=current_user['id'])
            purged.append({"id": user.id, "username": user.username})
        except Exception:
            continue

    repo_auditoria.registrar_accion(
        usuario_id=current_user['id'],
        tipo_accion="ELIMINAR",
        tabla="usuarios",
        descripcion=f"Depuración masiva de usuarios: {len(purged)} eliminados",
        datos_nuevos=json.dumps(purged, ensure_ascii=False),
        resultado="SUCCESS"
    )
    return {"status": "success", "purged": purged, "count": len(purged)}


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