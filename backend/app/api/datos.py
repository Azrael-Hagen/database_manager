"""Endpoints CRUD para datos importados."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database.orm import get_db
from app.models import DatoImportado as DatoImportadoModel
from app.database.repositorios import RepositorioDatoImportado, RepositorioAuditoria
from app.schemas import DatoImportado, DatoImportadoCrear, DatoImportadoActualizar, RespuestaPaginada
from app.security import (
    ROLE_CAPTURE,
    get_current_user,
    require_admin_role,
    require_capture_role,
    require_super_admin_role,
    require_server_machine_request,
)
from app.models import PapeleraRegistro
from fastapi import Request
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/datos", tags=["Datos"])


def _dato_to_snapshot(dato: DatoImportadoModel) -> dict:
    """Serializar un DatoImportado a dict para snapshot de papelera."""
    return {
        "id": dato.id,
        "uuid": dato.uuid,
        "nombre": dato.nombre,
        "email": dato.email,
        "telefono": dato.telefono,
        "empresa": dato.empresa,
        "ciudad": dato.ciudad,
        "pais": dato.pais,
        "datos_adicionales": dato.datos_adicionales,
        "estatus_codigo": dato.estatus_codigo,
        "qr_filename": dato.qr_filename,
        "contenido_qr": dato.contenido_qr,
        "creado_por": dato.creado_por,
        "fecha_creacion": dato.fecha_creacion.isoformat() if dato.fecha_creacion else None,
        "fecha_modificacion": dato.fecha_modificacion.isoformat() if dato.fecha_modificacion else None,
        "es_activo": dato.es_activo,
    }


def _guardar_snapshot_papelera(
    db: Session,
    dato: DatoImportadoModel,
    tipo: str,
    borrado_por: int,
) -> None:
    """Guarda un snapshot del registro en papelera antes de eliminarlo."""
    snap = PapeleraRegistro(
        tabla="datos_importados",
        registro_id=dato.id,
        snapshot_json=json.dumps(_dato_to_snapshot(dato), ensure_ascii=False),
        tipo_borrado=tipo,
        borrado_por=borrado_por,
    )
    db.add(snap)


def _safe_json_object(raw: str | dict | None) -> dict:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _legacy_text(raw: str | None, max_len: int) -> str:
    value = str(raw or "").strip()
    if len(value) > max_len:
        return value[:max_len]
    return value


def _sync_legacy_agente_row(db: Session, *, agente_id: int, nombre: str, datos_adicionales: dict | None = None) -> None:
    dialect = getattr(getattr(db, "bind", None), "dialect", None)
    if getattr(dialect, "name", "") == "sqlite":
        return
    extras = datos_adicionales if isinstance(datos_adicionales, dict) else {}
    db.execute(
        text(
            """
            INSERT INTO `registro_agentes`.`agentes`
                (`ID`, `Nombre`, `alias`, `Ubicacion`, `FP`, `FC`, `Grupo`)
            VALUES
                (:id, :nombre, :alias, :ubicacion, :fp, :fc, :grupo)
            ON DUPLICATE KEY UPDATE
                `Nombre` = VALUES(`Nombre`),
                `alias` = VALUES(`alias`),
                `Ubicacion` = VALUES(`Ubicacion`),
                `FP` = VALUES(`FP`),
                `FC` = VALUES(`FC`),
                `Grupo` = VALUES(`Grupo`)
            """
        ),
        {
            "id": int(agente_id),
            "nombre": _legacy_text(nombre, 50),
            "alias": _legacy_text(extras.get("alias"), 50),
            "ubicacion": _legacy_text(extras.get("ubicacion"), 10),
            "fp": _legacy_text(extras.get("fp"), 10),
            "fc": _legacy_text(extras.get("fc"), 10),
            "grupo": _legacy_text(extras.get("grupo"), 10),
        },
    )


def _delete_legacy_agente_row(db: Session, agente_id: int) -> None:
    dialect = getattr(getattr(db, "bind", None), "dialect", None)
    if getattr(dialect, "name", "") == "sqlite":
        return
    db.execute(
        text("DELETE FROM `registro_agentes`.`agentes` WHERE `ID` = :id"),
        {"id": int(agente_id)},
    )


@router.get("/", response_model=RespuestaPaginada)
async def listar_datos(
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(10, ge=1, le=100),
    todos: bool = Query(False),
    buscar: str = Query(None),
    ordenar_por: str = Query("fecha_creacion"),
    direccion: str = Query("desc"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Listar datos importados con paginación y búsqueda."""
    allowed_fields = {
        "id": DatoImportadoModel.id,
        "nombre": DatoImportadoModel.nombre,
        "email": DatoImportadoModel.email,
        "telefono": DatoImportadoModel.telefono,
        "ciudad": DatoImportadoModel.ciudad,
        "pais": DatoImportadoModel.pais,
        "fecha_creacion": DatoImportadoModel.fecha_creacion,
        "fecha_modificacion": DatoImportadoModel.fecha_modificacion,
        "uuid": DatoImportadoModel.uuid,
    }
    order_field = allowed_fields.get((ordenar_por or "").strip(), DatoImportadoModel.fecha_creacion)
    direction_value = (direccion or "desc").strip().lower()
    order_clause = order_field.desc() if direction_value != "asc" else order_field.asc()

    query = db.query(DatoImportadoModel).filter(DatoImportadoModel.es_activo.is_(True))
    if buscar:
        term = f"%{buscar}%"
        query = query.filter(
            (DatoImportadoModel.nombre.ilike(term)) |
            (DatoImportadoModel.email.ilike(term)) |
            (DatoImportadoModel.telefono.ilike(term)) |
            (DatoImportadoModel.ciudad.ilike(term)) |
            (DatoImportadoModel.pais.ilike(term))
        )

    total = query.count()
    skip = 0 if todos else (pagina - 1) * por_pagina
    effective_limit = max(total, 1) if todos else por_pagina
    registros = query.order_by(order_clause, DatoImportadoModel.id.desc()).offset(skip).limit(effective_limit).all()
    
    respuesta_por_pagina = total if todos else por_pagina
    total_paginas = 1 if todos else (total + por_pagina - 1) // por_pagina
    
    return {
        "status": "success",
        "data": registros,
        "pagina": 1 if todos else pagina,
        "por_pagina": respuesta_por_pagina,
        "total": total,
        "total_paginas": total_paginas
    }


@router.get("/{dato_id}", response_model=DatoImportado)
async def obtener_dato(
    dato_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener dato por ID."""
    repo = RepositorioDatoImportado(db)
    dato = repo.obtener_por_id(dato_id)
    
    if not dato or not dato.es_activo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dato no encontrado"
        )
    
    return dato


@router.get("/uuid/{uuid}", response_model=DatoImportado)
async def obtener_dato_por_uuid(
    uuid: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener dato por UUID."""
    repo = RepositorioDatoImportado(db)
    dato = repo.obtener_por_uuid(uuid)
    
    if not dato or not dato.es_activo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dato no encontrado"
        )
    
    return dato


@router.post("/", response_model=DatoImportado)
async def crear_dato(
    dato_in: DatoImportadoCrear,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Crear nuevo dato."""
    require_capture_role(current_user)
    repo = RepositorioDatoImportado(db)
    repo_auditoria = RepositorioAuditoria(db)
    
    dato_dict = dato_in.model_dump()
    dato_dict['creado_por'] = current_user['id']
    
    dato = repo.crear(dato_in)

    try:
        _sync_legacy_agente_row(
            db,
            agente_id=dato.id,
            nombre=dato.nombre,
            datos_adicionales=_safe_json_object(dato.datos_adicionales),
        )
        db.commit()
    except Exception as exc:
        logger.exception("No se pudo sincronizar alta en registro_agentes.agentes")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible guardar el agente en registro_agentes.agentes",
        ) from exc
    
    # Auditoría
    repo_auditoria.registrar_accion(
        usuario_id=current_user['id'],
        tipo_accion="CREAR",
        tabla="datos_importados",
        registro_id=dato.id,
        descripcion=f"Dato creado: {dato.nombre}",
        datos_nuevos=json.dumps(dato_in.model_dump()),
        resultado="SUCCESS"
    )
    
    return dato


@router.put("/{dato_id}", response_model=DatoImportado)
async def actualizar_dato(
    dato_id: int,
    dato_in: DatoImportadoActualizar,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Actualizar dato existente."""
    require_admin_role(current_user, "Solo administradores pueden modificar registros existentes")
    repo = RepositorioDatoImportado(db)
    repo_auditoria = RepositorioAuditoria(db)
    
    dato = repo.obtener_por_id(dato_id)
    if not dato or not dato.es_activo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dato no encontrado"
        )
    
    # Datos anteriores para auditoría
    datos_anteriores = {
        "nombre": dato.nombre,
        "email": dato.email,
        "telefono": dato.telefono,
        "empresa": dato.empresa
    }
    
    update_data = dato_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        if field == "datos_adicionales" and value is not None:
            clean_json = {k: v for k, v in value.items() if v not in (None, "")}
            setattr(dato, field, json.dumps(clean_json, ensure_ascii=False) if clean_json else None)
        else:
            setattr(dato, field, value)

    try:
        _sync_legacy_agente_row(
            db,
            agente_id=dato.id,
            nombre=dato.nombre,
            datos_adicionales=_safe_json_object(dato.datos_adicionales),
        )
    except Exception as exc:
        logger.exception("No se pudo sincronizar actualizacion en registro_agentes.agentes")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible actualizar el agente en registro_agentes.agentes",
        ) from exc

    db.add(dato)
    db.commit()
    db.refresh(dato)
    
    # Auditoría
    repo_auditoria.registrar_accion(
        usuario_id=current_user['id'],
        tipo_accion="ACTUALIZAR",
        tabla="datos_importados",
        registro_id=dato_id,
        descripcion=f"Dato actualizado: {dato.nombre}",
        datos_anteriores=json.dumps(datos_anteriores),
        datos_nuevos=json.dumps(dato_in.dict(exclude_unset=True)),
        resultado="SUCCESS"
    )
    
    return dato


@router.delete("/{dato_id}")
async def eliminar_dato(
    dato_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Eliminar (soft delete) dato."""
    require_admin_role(current_user, "Solo administradores pueden eliminar registros")
    repo = RepositorioDatoImportado(db)
    repo_auditoria = RepositorioAuditoria(db)
    
    dato = repo.obtener_por_id(dato_id)
    if not dato or not dato.es_activo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dato no encontrado"
        )
    
    _guardar_snapshot_papelera(db, dato, "soft", current_user['id'])

    dato.es_activo = False
    dato.estatus_codigo = "BAJA"
    dato.fecha_eliminacion = datetime.utcnow()

    try:
        _delete_legacy_agente_row(db, dato_id)
    except Exception as exc:
        logger.exception("No se pudo sincronizar baja en registro_agentes.agentes")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible aplicar la baja en registro_agentes.agentes",
        ) from exc

    db.add(dato)
    db.commit()
    
    # Auditoría
    repo_auditoria.registrar_accion(
        usuario_id=current_user['id'],
        tipo_accion="ELIMINAR",
        tabla="datos_importados",
        registro_id=dato_id,
        descripcion=f"Dato eliminado: {dato.nombre}",
        resultado="SUCCESS"
    )
    
    return {"status": "success", "mensaje": "Dato eliminado"}


@router.delete("/{dato_id}/hard-delete")
async def eliminar_dato_definitivo(
    dato_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Eliminar definitivamente un dato y sus dependencias operativas. Solo super_admin."""
    require_super_admin_role(current_user, "Solo super administradores pueden eliminar definitivamente registros")

    repo = RepositorioDatoImportado(db)
    repo_auditoria = RepositorioAuditoria(db)
    dato = repo.obtener_por_id(dato_id)
    if not dato:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dato no encontrado")

    _guardar_snapshot_papelera(db, dato, "hard", current_user['id'])
    db.flush()
    repo.eliminar_definitivo(dato_id)
    try:
        _delete_legacy_agente_row(db, dato_id)
        db.commit()
    except Exception:
        logger.warning("No se pudo eliminar registro legado para agente %s", dato_id)
    repo_auditoria.registrar_accion(
        usuario_id=current_user['id'],
        tipo_accion="ELIMINAR",
        tabla="datos_importados",
        registro_id=dato_id,
        descripcion=f"Dato eliminado definitivamente: {dato.nombre}",
        resultado="SUCCESS"
    )
    return {"status": "success", "mensaje": "Dato eliminado definitivamente"}


@router.delete("/purge/inactivos")
async def purgar_datos_inactivos(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Eliminar definitivamente todos los datos marcados como inactivos. Solo super_admin."""
    require_super_admin_role(current_user, "Solo super administradores pueden purgar registros")
    require_server_machine_request(request)

    repo = RepositorioDatoImportado(db)
    repo_auditoria = RepositorioAuditoria(db)
    deleted = repo.purgar_inactivos()
    repo_auditoria.registrar_accion(
        usuario_id=current_user['id'],
        tipo_accion="ELIMINAR",
        tabla="datos_importados",
        descripcion=f"Purgados definitivamente {deleted} registros inactivos",
        resultado="SUCCESS"
    )
    return {"status": "success", "mensaje": f"Se eliminaron definitivamente {deleted} registros inactivos", "deleted": deleted}


@router.get("/papelera")
async def listar_papelera(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """Listar registros en la papelera de reciclaje. Solo super_admin."""
    require_super_admin_role(current_user, "Solo super administradores pueden ver la papelera")
    registros = (
        db.query(PapeleraRegistro)
        .order_by(PapeleraRegistro.fecha_borrado.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "tabla": r.tabla,
            "registro_id": r.registro_id,
            "snapshot_json": json.loads(r.snapshot_json) if r.snapshot_json else {},
            "tipo_borrado": r.tipo_borrado,
            "borrado_por": r.borrado_por,
            "fecha_borrado": r.fecha_borrado.isoformat() if r.fecha_borrado else None,
            "restaurado": r.restaurado,
            "fecha_restauracion": r.fecha_restauracion.isoformat() if r.fecha_restauracion else None,
            "restaurado_por": r.restaurado_por,
        }
        for r in registros
    ]


@router.post("/{dato_id}/rollback")
async def rollback_dato(
    dato_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Restaurar un registro eliminado desde la papelera. Solo super_admin."""
    require_super_admin_role(current_user, "Solo super administradores pueden realizar rollback")

    snap = (
        db.query(PapeleraRegistro)
        .filter(
            PapeleraRegistro.registro_id == dato_id,
            PapeleraRegistro.tabla == "datos_importados",
            PapeleraRegistro.restaurado == False,
        )
        .order_by(PapeleraRegistro.fecha_borrado.desc())
        .first()
    )
    if not snap:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró un snapshot restaurable para este registro",
        )

    snapshot = json.loads(snap.snapshot_json)
    repo = RepositorioDatoImportado(db)
    repo_auditoria = RepositorioAuditoria(db)

    existing = db.query(DatoImportadoModel).filter(DatoImportadoModel.id == dato_id).first()
    if existing:
        # Reactivar el registro existente
        existing.es_activo = True
        existing.estatus_codigo = snapshot.get("estatus_codigo", "ACTIVO")
        existing.fecha_eliminacion = None
        db.add(existing)
    else:
        # Recrear desde snapshot (solo si fue hard-deleted)
        nuevo = DatoImportadoModel(
            id=snapshot.get("id"),
            uuid=snapshot.get("uuid"),
            nombre=snapshot.get("nombre"),
            email=snapshot.get("email"),
            telefono=snapshot.get("telefono"),
            empresa=snapshot.get("empresa"),
            ciudad=snapshot.get("ciudad"),
            pais=snapshot.get("pais"),
            datos_adicionales=snapshot.get("datos_adicionales"),
            estatus_codigo=snapshot.get("estatus_codigo", "ACTIVO"),
            qr_filename=snapshot.get("qr_filename"),
            contenido_qr=snapshot.get("contenido_qr"),
            creado_por=snapshot.get("creado_por"),
            es_activo=True,
        )
        db.add(nuevo)

    snap.restaurado = True
    snap.fecha_restauracion = datetime.utcnow()
    snap.restaurado_por = current_user['id']
    db.add(snap)
    db.commit()

    repo_auditoria.registrar_accion(
        usuario_id=current_user['id'],
        tipo_accion="RESTAURAR",
        tabla="datos_importados",
        registro_id=dato_id,
        descripcion=f"Rollback ejecutado para registro id={dato_id}",
        resultado="SUCCESS",
    )

    return {"status": "success", "mensaje": f"Registro {dato_id} restaurado correctamente"}
