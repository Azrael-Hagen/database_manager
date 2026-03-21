"""Endpoints CRUD para datos importados."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database.orm import get_db
from app.database.repositorios import RepositorioDatoImportado, RepositorioAuditoria
from app.schemas import DatoImportado, DatoImportadoCrear, DatoImportadoActualizar, RespuestaPaginada
from app.security import get_current_user
from fastapi import Request
import logging
import json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/datos", tags=["Datos"])


@router.get("/", response_model=RespuestaPaginada)
async def listar_datos(
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(10, ge=1, le=100),
    buscar: str = Query(None),
    ordenar_por: str = Query("fecha_creacion"),
    direccion: str = Query("desc"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Listar datos importados con paginación y búsqueda."""
    repo = RepositorioDatoImportado(db)
    
    skip = (pagina - 1) * por_pagina
    
    registros, total = repo.buscar(
        buscar=buscar,
        skip=skip,
        limit=por_pagina
    )
    
    total_paginas = (total + por_pagina - 1) // por_pagina
    
    return {
        "status": "success",
        "data": registros,
        "pagina": pagina,
        "por_pagina": por_pagina,
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
