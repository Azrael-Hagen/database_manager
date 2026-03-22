"""Endpoints CRUD para datos importados."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database.orm import get_db
from app.models import DatoImportado as DatoImportadoModel
from app.database.repositorios import RepositorioDatoImportado, RepositorioAuditoria
from app.schemas import DatoImportado, DatoImportadoCrear, DatoImportadoActualizar, RespuestaPaginada
from app.security import ROLE_CAPTURE, get_current_user, require_admin_role, require_capture_role, require_server_machine_request
from fastapi import Request
import logging
import json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/datos", tags=["Datos"])


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
    
    dato_dict = dato_in.dict()
    dato_dict['creado_por'] = current_user['id']
    
    dato = repo.crear(dato_in)
    
    # Auditoría
    repo_auditoria.registrar_accion(
        usuario_id=current_user['id'],
        tipo_accion="CREAR",
        tabla="datos_importados",
        registro_id=dato.id,
        descripcion=f"Dato creado: {dato.nombre}",
        datos_nuevos=json.dumps(dato_in.dict()),
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
    
    dato_actualizado = repo.actualizar(dato_id, dato_in)
    
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
    
    return dato_actualizado


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
    
    repo.eliminar(dato_id)
    
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
    """Eliminar definitivamente un dato y sus dependencias operativas."""
    require_admin_role(current_user, "Solo administradores pueden eliminar definitivamente registros")

    repo = RepositorioDatoImportado(db)
    repo_auditoria = RepositorioAuditoria(db)
    dato = repo.obtener_por_id(dato_id)
    if not dato:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dato no encontrado")

    repo.eliminar_definitivo(dato_id)
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
    """Eliminar definitivamente todos los datos marcados como inactivos."""
    require_admin_role(current_user, "Solo administradores pueden purgar registros")
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
