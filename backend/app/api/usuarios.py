"""Endpoints para gestión de usuarios."""

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body, Request
from sqlalchemy.orm import Session
from app.database.orm import get_db
from app.database.repositorios import RepositorioUsuario, RepositorioAuditoria
from app.schemas import (
    Usuario,
    UsuarioCrear,
    UsuarioActualizar,
    PasswordUpdate,
    UsuarioTemporalCrear,
    UsuarioTemporalRenovar,
    SolicitudPermisoCrear,
    SolicitudPermisoResolver,
    TempUsuarioHistorialItem,
)
from app.security import (
    normalize_role,
    get_current_user,
    hash_password,
    require_admin_role,
    require_server_machine_request,
    ROLE_ADMIN,
    ROLE_CAPTURE,
    require_super_admin_role,
)
from app.models import Usuario as UsuarioModel, TempUsuarioHistorial
import logging
import json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/usuarios", tags=["User Management"])

TEMP_USER_PREFIXES = ("tmp_", "temp_", "test_", "demo_")
TEMP_USER_MAX_DAYS = 10


ROLE_CAPABILITIES = [
    {
        "role": "viewer",
        "label": "Consulta",
        "description": "Solo lectura operativa y seguimiento de alertas.",
        "permissions": [
            "Ver dashboard",
            "Consultar datos",
            "Leer alertas y marcarlas como leidas",
        ],
    },
    {
        "role": "capture",
        "label": "Altas",
        "description": "Operacion de captura, importacion y estado de agentes.",
        "permissions": [
            "Todo lo de Consulta",
            "Importar y exportar",
            "Altas de agentes y gestion de lineas",
            "Estado de agentes",
        ],
    },
    {
        "role": "admin",
        "label": "Administrador",
        "description": "Control operativo completo y administracion de usuarios.",
        "permissions": [
            "Todo lo de Altas",
            "Cambios y bajas",
            "Escaneo QR y QR/Cobros",
            "Gestion de usuarios y auditoria",
            "Enviar/desactivar alertas del sistema",
        ],
    },
    {
        "role": "super_admin",
        "label": "Super Admin",
        "description": "Nivel maximo: gobierno de permisos y operaciones criticas.",
        "permissions": [
            "Todo lo de Administrador",
            "Asignar/crear otros super_admin",
            "Operaciones de papelera y purga critica",
            "Controles avanzados de seguridad",
        ],
    },
]


def _archive_temp_user(
    db: Session,
    user: UsuarioModel,
    motivo: str,
    eliminado_por: int | None = None,
    detalle: dict | None = None,
) -> None:
    payload = TempUsuarioHistorial(
        usuario_id=user.id,
        username=user.username,
        email=user.email,
        rol=normalize_role(user.rol, user.es_admin),
        fecha_creacion_usuario=user.fecha_creacion,
        fecha_expiracion=user.temporal_expira_en,
        fecha_eliminacion=datetime.now(timezone.utc),
        motivo=motivo,
        eliminado_por=eliminado_por,
        detalle_json=json.dumps(detalle or {}, ensure_ascii=False),
    )
    db.add(payload)


def _purge_expired_temp_users(db: Session, actor_user_id: int | None = None) -> list[dict]:
    now = datetime.now(timezone.utc)
    repo = RepositorioUsuario(db)
    expired = (
        db.query(UsuarioModel)
        .filter(
            UsuarioModel.es_temporal.is_(True),
            UsuarioModel.temporal_expira_en.isnot(None),
            UsuarioModel.temporal_expira_en <= now,
        )
        .all()
    )
    purged: list[dict] = []
    for user in expired:
        if actor_user_id and user.id == actor_user_id:
            continue
        try:
            _archive_temp_user(
                db,
                user,
                motivo="expirado",
                eliminado_por=actor_user_id,
                detalle={"trigger": "auto-expiry"},
            )
            repo.eliminar_usuario_definitivo(user.id, reassigned_user_id=actor_user_id)
            purged.append({"id": user.id, "username": user.username})
        except Exception as exc:
            logger.warning("No se pudo eliminar usuario temporal expirado %s: %s", user.username, exc)
            db.rollback()
    return purged


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

    _purge_expired_temp_users(db, actor_user_id=current_user["id"])

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


@router.get("/roles/capabilities")
async def listar_capacidades_roles(
    current_user: dict = Depends(get_current_user),
):
    """Matriz de capacidades por rol para consumo de UI y soporte operativo."""
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado")

    return {
        "status": "success",
        "total": len(ROLE_CAPABILITIES),
        "items": ROLE_CAPABILITIES,
    }


@router.post("/temporales", response_model=Usuario)
async def crear_usuario_temporal(
    payload: UsuarioTemporalCrear,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Crear usuario temporal de solo consulta con vigencia máxima de 10 días."""
    require_admin_role(current_user, "Solo administradores pueden crear usuarios temporales")

    repo = RepositorioUsuario(db)
    repo_auditoria = RepositorioAuditoria(db)

    if repo.obtener_por_username(payload.username):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El nombre de usuario ya existe")
    if repo.obtener_por_email(payload.email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El email ya está registrado")

    dias_vigencia = min(int(payload.dias_vigencia or TEMP_USER_MAX_DAYS), TEMP_USER_MAX_DAYS)
    expira_en = datetime.now(timezone.utc) + timedelta(days=dias_vigencia)
    user_data = {
        "username": payload.username,
        "email": payload.email,
        "nombre_completo": payload.nombre_completo,
        "hashed_password": hash_password(payload.password),
        "rol": "viewer",
        "es_admin": False,
        "es_activo": True,
        "es_temporal": True,
        "temporal_expira_en": expira_en,
        "temporal_renovaciones": 0,
        "solicitud_permiso_estado": "none",
    }
    usuario = repo.crear_usuario(user_data)

    repo_auditoria.registrar_accion(
        usuario_id=current_user["id"],
        tipo_accion="CREAR",
        tabla="usuarios",
        registro_id=usuario.id,
        descripcion=f"Usuario temporal creado: {usuario.username}",
        datos_nuevos=json.dumps({"dias_vigencia": dias_vigencia, "expira_en": expira_en.isoformat()}, ensure_ascii=False),
        resultado="SUCCESS",
    )
    return usuario


@router.post("/{user_id}/temporal/renovar", response_model=Usuario)
async def renovar_usuario_temporal(
    user_id: int,
    payload: UsuarioTemporalRenovar,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Renovar vigencia de un usuario temporal por hasta 10 días."""
    require_admin_role(current_user, "Solo administradores pueden renovar usuarios temporales")

    repo = RepositorioUsuario(db)
    repo_auditoria = RepositorioAuditoria(db)
    usuario = repo.obtener_por_id(user_id)
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    if not usuario.es_temporal:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El usuario no es temporal")

    dias_vigencia = min(int(payload.dias_vigencia or TEMP_USER_MAX_DAYS), TEMP_USER_MAX_DAYS)
    nueva_expiracion = datetime.now(timezone.utc) + timedelta(days=dias_vigencia)
    usuario_actualizado = repo.actualizar_usuario(
        user_id,
        {
            "temporal_expira_en": nueva_expiracion,
            "temporal_renovaciones": int(usuario.temporal_renovaciones or 0) + 1,
        },
    )

    repo_auditoria.registrar_accion(
        usuario_id=current_user["id"],
        tipo_accion="ACTUALIZAR",
        tabla="usuarios",
        registro_id=user_id,
        descripcion=f"Renovación de temporal: {usuario.username}",
        datos_nuevos=json.dumps({"expira_en": nueva_expiracion.isoformat(), "dias": dias_vigencia}, ensure_ascii=False),
        resultado="SUCCESS",
    )
    return usuario_actualizado


@router.post("/{user_id}/solicitud-permisos", response_model=Usuario)
async def solicitar_escalamiento_permisos(
    user_id: int,
    payload: SolicitudPermisoCrear,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Registrar solicitud de escalamiento para usuario temporal."""
    requester_id = int(current_user.get("id") or 0)
    is_admin = bool(current_user.get("es_admin"))
    if requester_id != user_id and not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo puedes solicitar permisos para tu propio usuario")

    repo = RepositorioUsuario(db)
    repo_auditoria = RepositorioAuditoria(db)
    usuario = repo.obtener_por_id(user_id)
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    if not usuario.es_temporal:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Solo aplica para usuarios temporales")

    rol_solicitado = ROLE_ADMIN if payload.rol_solicitado == ROLE_ADMIN else ROLE_CAPTURE
    usuario_actualizado = repo.actualizar_usuario(
        user_id,
        {
            "solicitud_permiso_estado": "pending",
            "solicitud_permiso_rol": rol_solicitado,
            "solicitud_permiso_motivo": payload.motivo,
            "solicitud_permiso_fecha": datetime.now(timezone.utc),
        },
    )

    repo_auditoria.registrar_accion(
        usuario_id=requester_id or user_id,
        tipo_accion="ACTUALIZAR",
        tabla="usuarios",
        registro_id=user_id,
        descripcion=f"Solicitud de permisos temporal: {usuario.username}",
        datos_nuevos=json.dumps({"rol_solicitado": rol_solicitado, "motivo": payload.motivo or ""}, ensure_ascii=False),
        resultado="SUCCESS",
    )
    return usuario_actualizado


@router.get("/solicitudes-permisos")
async def listar_solicitudes_permisos(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Listar solicitudes de escalamiento pendientes para usuarios temporales."""
    require_admin_role(current_user, "Solo administradores pueden ver solicitudes")

    _purge_expired_temp_users(db, actor_user_id=current_user["id"])
    rows = (
        db.query(UsuarioModel)
        .filter(
            UsuarioModel.es_temporal.is_(True),
            UsuarioModel.solicitud_permiso_estado == "pending",
        )
        .order_by(UsuarioModel.solicitud_permiso_fecha.desc(), UsuarioModel.id.desc())
        .all()
    )
    return {
        "status": "success",
        "total": len(rows),
        "items": [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "rol_actual": normalize_role(u.rol, u.es_admin),
                "rol_solicitado": u.solicitud_permiso_rol,
                "motivo": u.solicitud_permiso_motivo,
                "solicitado_en": u.solicitud_permiso_fecha.isoformat() if u.solicitud_permiso_fecha else None,
                "expira_en": u.temporal_expira_en.isoformat() if u.temporal_expira_en else None,
            }
            for u in rows
        ],
    }


@router.post("/solicitudes-permisos/{user_id}/resolver", response_model=Usuario)
async def resolver_solicitud_permisos(
    user_id: int,
    payload: SolicitudPermisoResolver,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Aprobar o rechazar solicitud de permisos de usuario temporal."""
    require_admin_role(current_user, "Solo administradores pueden resolver solicitudes")

    repo = RepositorioUsuario(db)
    repo_auditoria = RepositorioAuditoria(db)
    usuario = repo.obtener_por_id(user_id)
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    if not usuario.es_temporal:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El usuario no es temporal")
    if (usuario.solicitud_permiso_estado or "none") != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No hay solicitud pendiente para este usuario")

    approved_role = ROLE_ADMIN if payload.rol_aprobado == ROLE_ADMIN else ROLE_CAPTURE
    if payload.aprobar:
        updates = {
            "rol": approved_role,
            "es_admin": approved_role == ROLE_ADMIN,
            "es_temporal": False,
            "temporal_expira_en": None,
            "solicitud_permiso_estado": "approved",
            "solicitud_permiso_rol": approved_role,
        }
    else:
        updates = {
            "solicitud_permiso_estado": "rejected",
        }

    usuario_actualizado = repo.actualizar_usuario(user_id, updates)

    repo_auditoria.registrar_accion(
        usuario_id=current_user["id"],
        tipo_accion="ACTUALIZAR",
        tabla="usuarios",
        registro_id=user_id,
        descripcion=f"Solicitud de permisos {'aprobada' if payload.aprobar else 'rechazada'}: {usuario.username}",
        datos_nuevos=json.dumps({"aprobar": payload.aprobar, "rol_aprobado": approved_role}, ensure_ascii=False),
        resultado="SUCCESS",
    )
    return usuario_actualizado


@router.get("/temporales/historial", response_model=list[TempUsuarioHistorialItem])
async def historial_temporales(
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Consultar historial de usuarios temporales autoeliminados o depurados."""
    require_admin_role(current_user, "Solo administradores pueden consultar historial")

    rows = db.query(TempUsuarioHistorial).order_by(TempUsuarioHistorial.fecha_eliminacion.desc()).limit(limit).all()
    return rows


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

    requested_role = normalize_role(usuario_in.rol, bool(usuario_in.es_admin))
    if requested_role == "super_admin":
        require_super_admin_role(current_user, "Solo super_admin puede crear otros super_admin")

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
    usuario_dict = usuario_in.model_dump()
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

    update_payload = usuario_in.model_dump(exclude_unset=True)
    requested_role = normalize_role(update_payload.get("rol"), bool(update_payload.get("es_admin", usuario.es_admin)))
    if requested_role == "super_admin":
        require_super_admin_role(current_user, "Solo super_admin puede asignar rol super_admin")

    usuario_actualizado = repo.actualizar_usuario(user_id, update_payload)

    # Auditoría
    repo_auditoria.registrar_accion(
        usuario_id=current_user['id'],
        tipo_accion="ACTUALIZAR",
        tabla="usuarios",
        registro_id=user_id,
        descripcion=f"Usuario actualizado: {usuario.username}",
        datos_anteriores=json.dumps(datos_anteriores),
        datos_nuevos=json.dumps(update_payload),
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

    now = datetime.now(timezone.utc)
    stale_cutoff = now - timedelta(days=60)
    users = db.query(UsuarioModel).order_by(UsuarioModel.fecha_creacion.desc()).all()

    candidates = []
    for user in users:
        username = (user.username or "").lower()
        is_temp_name = username.startswith(TEMP_USER_PREFIXES)
        is_temp_flag = bool(user.es_temporal)
        stale_session = user.fecha_ultima_sesion is None or user.fecha_ultima_sesion < stale_cutoff
        inactive = not bool(user.es_activo)
        if is_temp_name or is_temp_flag or (inactive and stale_session):
            candidates.append(
                {
                    "id": user.id,
                    "username": user.username,
                    "rol": normalize_role(user.rol, user.es_admin),
                    "es_activo": bool(user.es_activo),
                    "fecha_creacion": user.fecha_creacion.isoformat() if user.fecha_creacion else None,
                    "fecha_ultima_sesion": user.fecha_ultima_sesion.isoformat() if user.fecha_ultima_sesion else None,
                    "is_temp_name": is_temp_name,
                    "is_temp_flag": is_temp_flag,
                    "temporal_expira_en": user.temporal_expira_en.isoformat() if user.temporal_expira_en else None,
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

    stale_cutoff = datetime.now(timezone.utc) - timedelta(days=60)
    users = db.query(UsuarioModel).all()
    purged = []
    for user in users:
        if user.id == current_user['id']:
            continue
        role = normalize_role(user.rol, user.es_admin)
        username_lower = (user.username or "").lower()
        is_temp = bool(user.es_temporal) or username_lower.startswith(TEMP_USER_PREFIXES)
        is_stale_inactive = include_inactive_stale and (not user.es_activo) and (
            user.fecha_ultima_sesion is None or user.fecha_ultima_sesion < stale_cutoff
        )
        if role == "admin":
            continue
        if not is_temp and not is_stale_inactive:
            continue
        try:
            _archive_temp_user(
                db,
                user,
                motivo="purga_manual_temporales" if is_temp else "purga_manual_obsoleto",
                eliminado_por=current_user['id'],
                detalle={"include_inactive_stale": bool(include_inactive_stale)},
            )
            repo.eliminar_usuario_definitivo(user.id, reassigned_user_id=current_user['id'])
            purged.append({"id": user.id, "username": user.username})
        except Exception:
            db.rollback()
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