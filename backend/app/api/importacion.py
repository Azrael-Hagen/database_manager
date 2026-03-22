"""Endpoints mejorados para importación de archivos."""

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status, BackgroundTasks, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging
import os
import tempfile
from datetime import datetime
import time
import json
import re
from app.database.orm import get_db
from app.database.repositorios import RepositorioImportLog, RepositorioDatoImportado, RepositorioAuditoria
from app.models import ImportLog
from app.importers import CSVImporter, ExcelImporter, TextImporter
from app.qr import QRGenerator
from app.security import get_current_user, require_capture_role
from app.config import config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/import", tags=["Importación"])


def _crear_log_importacion(repo_import: RepositorioImportLog, log_data: dict) -> ImportLog:
    """Crear log de importación preservando todos los campos requeridos por el modelo."""
    log = ImportLog(**log_data)
    repo_import.db.add(log)
    repo_import.db.commit()
    repo_import.db.refresh(log)
    return log


def _safe_identifier(name: str) -> str:
    """Sanitizar identificador SQL (tabla o columna)."""
    cleaned = re.sub(r'[^a-zA-Z0-9_]', '_', (name or '').strip())
    if not cleaned:
        raise ValueError("Nombre inválido")
    return cleaned


def _serialize_cell(value):
    """Normalizar valor para inserción SQL."""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _ensure_table_and_columns(db: Session, table_name: str, columns: list[str]):
    """Crear tabla si no existe y agregar columnas faltantes."""
    safe_table = _safe_identifier(table_name)
    safe_columns = [_safe_identifier(col) for col in columns if col and str(col).strip()]

    exists_query = text(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = :table_name
        """
    )
    exists = db.execute(exists_query, {"table_name": safe_table}).scalar()

    if not exists:
        create_cols = ["`id` INT AUTO_INCREMENT PRIMARY KEY", "`created_at` DATETIME DEFAULT CURRENT_TIMESTAMP"]
        create_cols.extend([f"`{col}` TEXT NULL" for col in safe_columns])
        db.execute(text(f"CREATE TABLE `{safe_table}` ({', '.join(create_cols)}) ENGINE=InnoDB"))
        db.commit()
        return safe_table, safe_columns

    current_cols_result = db.execute(text(f"SHOW COLUMNS FROM `{safe_table}`"))
    current_cols = {row[0] for row in current_cols_result.fetchall()}

    for col in safe_columns:
        if col not in current_cols:
            db.execute(text(f"ALTER TABLE `{safe_table}` ADD COLUMN `{col}` TEXT NULL"))

    db.commit()
    return safe_table, safe_columns


def _insert_rows_dynamic(db: Session, table_name: str, rows: list[dict]) -> tuple[int, int]:
    """Insertar filas dinámicas en tabla destino."""
    if not rows:
        return 0, 0

    raw_columns = list(rows[0].keys())
    safe_table, safe_columns = _ensure_table_and_columns(db, table_name, raw_columns)

    if not safe_columns:
        return 0, len(rows)

    columns_sql = ", ".join([f"`{col}`" for col in safe_columns])
    values_sql = ", ".join([f":{col}" for col in safe_columns])
    stmt = text(f"INSERT INTO `{safe_table}` ({columns_sql}) VALUES ({values_sql})")

    ok = 0
    failed = 0
    for row in rows:
        payload = {}
        for original_key, value in row.items():
            safe_key = _safe_identifier(str(original_key))
            if safe_key in safe_columns:
                payload[safe_key] = _serialize_cell(value)
        try:
            db.execute(stmt, payload)
            ok += 1
        except Exception:
            failed += 1

    db.commit()
    return ok, failed


def procesar_importacion(
    archivo_path: str,
    tipo_archivo: str,
    tabla_destino: str,
    delimitador: str,
    usuario_id: int,
    importacion_id: int,
    db: Session,
    db_session_factory
):
    """Procesar importación en background."""
    try:
        inicio = time.time()
        repo_import = RepositorioImportLog(db)
        repo_datos = RepositorioDatoImportado(db)
        repo_auditoria = RepositorioAuditoria(db)
        
        # Seleccionar importador
        if tipo_archivo.upper() == "CSV":
            importer = CSVImporter(archivo_path, tabla_destino, delimiter=delimitador)
        elif tipo_archivo.upper() == "EXCEL":
            importer = ExcelImporter(archivo_path, tabla_destino)
        else:  # TXT o DAT
            importer = TextImporter(archivo_path, tabla_destino, delimiter=delimitador)
        
        # Leer y validar
        if not importer.read_file():
            raise Exception(f"Error leyendo archivo: {importer.errors}")
        
        if not importer.validate_data():
            raise Exception(f"Validación fallida: {importer.errors}")
        
        # Insertar de forma adaptable en la tabla destino
        registros_importados, errores_insert = _insert_rows_dynamic(db, tabla_destino, importer.data)
        registros_fallidos = errores_insert
        
        # Calcular duración
        duracion = int(time.time() - inicio)
        
        # Actualizar log
        estado = "SUCCESS" if registros_fallidos == 0 else ("PARTIAL" if registros_importados > 0 else "FAILED")
        repo_import.actualizar_completado(
            importacion_id=importacion_id,
            registros_importados=registros_importados,
            registros_fallidos=registros_fallidos,
            estado=estado,
            duracion=duracion,
            mensaje_error=None if estado == "SUCCESS" else f"{registros_fallidos} registros fallidos"
        )
        
        # Auditoría
        repo_auditoria.registrar_accion(
            usuario_id=usuario_id,
            tipo_accion="IMPORTAR",
            tabla=tabla_destino,
            descripcion=f"Importación completada: {registros_importados} registros",
            resultado=estado
        )
        
        logger.info(f"Importación {importacion_id} completada: {registros_importados} importados, {registros_fallidos} fallidos")
        
    except Exception as e:
        logger.error(f"Error en importación {importacion_id}: {e}")
        repo_import = RepositorioImportLog(db)
        repo_import.actualizar_completado(
            importacion_id=importacion_id,
            registros_importados=0,
            registros_fallidos=0,
            estado="FAILED",
            duracion=int(time.time() - inicio),
            mensaje_error=str(e)
        )
    finally:
        # Limpiar archivo temporal
        try:
            os.remove(archivo_path)
        except:
            pass


@router.post("/csv")
async def importar_csv(
    archivo: UploadFile = File(None),
    file: UploadFile = File(None),
    tabla: str = Form(...),
    delimitador: str = Form(default=","),
    background_tasks: BackgroundTasks = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Importar archivo CSV."""
    require_capture_role(current_user)
    try:
        archivo_subido = archivo or file
        if not archivo_subido:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Debe enviar un archivo")

        repo_import = RepositorioImportLog(db)
        
        # Guardar archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp_file:
            contenido = await archivo_subido.read()
            tmp_file.write(contenido)
            temp_path = tmp_file.name
        
        # Crear log de importación
        log_data = {
            "archivo_nombre": archivo_subido.filename,
            "archivo_tamanio": len(contenido),
            "tipo_archivo": "CSV",
            "tabla_destino": tabla,
            "delimitador": delimitador,
            "registros_totales": 0,
            "usuario_id": current_user["id"],
            "estado": "PENDING"
        }
        
        log = _crear_log_importacion(repo_import, log_data)
        
        # Procesar en background
        if background_tasks:
            from app.database.orm import SessionLocal
            background_tasks.add_task(
                procesar_importacion,
                temp_path, "CSV", tabla, delimitador,
                current_user["id"], log.id, db, SessionLocal
            )
        
        return {
            "status": "success",
            "mensaje": "Importación iniciada",
            "importacion_id": log.id,
            "uuid": log.uuid
        }
    
    except Exception as e:
        logger.error(f"Error en importación CSV: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/excel")
async def importar_excel(
    archivo: UploadFile = File(None),
    file: UploadFile = File(None),
    tabla: str = Form(...),
    hoja: str = Form(default="0"),
    background_tasks: BackgroundTasks = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Importar archivo Excel."""
    require_capture_role(current_user)
    try:
        archivo_subido = archivo or file
        if not archivo_subido:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Debe enviar un archivo")

        repo_import = RepositorioImportLog(db)
        
        # Guardar archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_file:
            contenido = await archivo_subido.read()
            tmp_file.write(contenido)
            temp_path = tmp_file.name
        
        # Crear log
        log_data = {
            "archivo_nombre": archivo_subido.filename,
            "archivo_tamanio": len(contenido),
            "tipo_archivo": "EXCEL",
            "tabla_destino": tabla,
            "registros_totales": 0,
            "usuario_id": current_user["id"],
            "estado": "PENDING"
        }
        
        log = _crear_log_importacion(repo_import, log_data)
        
        # Procesar en background
        if background_tasks:
            from app.database.orm import SessionLocal
            background_tasks.add_task(
                procesar_importacion,
                temp_path, "EXCEL", tabla, "",
                current_user["id"], log.id, db, SessionLocal
            )
        
        return {
            "status": "success",
            "mensaje": "Importación iniciada",
            "importacion_id": log.id,
            "uuid": log.uuid
        }
    
    except Exception as e:
        logger.error(f"Error en importación Excel: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/txt")
async def importar_txt(
    archivo: UploadFile = File(None),
    file: UploadFile = File(None),
    tabla: str = Form(...),
    delimitador: str = Form(default="|"),
    background_tasks: BackgroundTasks = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Importar archivo TXT delimitado."""
    require_capture_role(current_user)
    archivo_subido = archivo or file
    if not archivo_subido:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Debe enviar un archivo")

    repo_import = RepositorioImportLog(db)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp_file:
        contenido = await archivo_subido.read()
        tmp_file.write(contenido)
        temp_path = tmp_file.name

    log = _crear_log_importacion(repo_import, {
        "archivo_nombre": archivo_subido.filename,
        "archivo_tamanio": len(contenido),
        "tipo_archivo": "TXT",
        "tabla_destino": tabla,
        "delimitador": delimitador,
        "registros_totales": 0,
        "usuario_id": current_user["id"],
        "estado": "PENDING"
    })

    if background_tasks:
        from app.database.orm import SessionLocal
        background_tasks.add_task(
            procesar_importacion,
            temp_path, "TXT", tabla, delimitador,
            current_user["id"], log.id, db, SessionLocal
        )

    return {"status": "success", "mensaje": "Importación iniciada", "importacion_id": log.id, "uuid": log.uuid}


@router.post("/dat")
async def importar_dat(
    archivo: UploadFile = File(None),
    file: UploadFile = File(None),
    tabla: str = Form(...),
    delimitador: str = Form(default="|"),
    background_tasks: BackgroundTasks = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Importar archivo DAT delimitado."""
    require_capture_role(current_user)
    return await importar_txt(
        archivo=archivo,
        file=file,
        tabla=tabla,
        delimitador=delimitador,
        background_tasks=background_tasks,
        current_user=current_user,
        db=db
    )


@router.get("/estado/{importacion_id}")
async def obtener_estado_importacion(
    importacion_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener estado de una importación."""
    repo = RepositorioImportLog(db)
    log = repo.obtener_por_id(importacion_id)
    
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Importación no encontrada"
        )
    
    if log.usuario_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado"
        )
    
    return {
        "status": "success",
        "data": {
            "id": log.id,
            "uuid": log.uuid,
            "archivo": log.archivo_nombre,
            "tabla": log.tabla_destino,
            "estado": log.estado,
            "registros_importados": log.registros_importados,
            "registros_fallidos": log.registros_fallidos,
            "registros_totales": log.registros_totales,
            "fecha_inicio": log.fecha_inicio,
            "fecha_fin": log.fecha_fin,
            "duracion_segundos": log.duracion_segundos
        }
    }
