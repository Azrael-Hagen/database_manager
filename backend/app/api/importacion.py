"""Endpoints mejorados para importación de archivos."""

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status, BackgroundTasks, Request
from sqlalchemy.orm import Session
import logging
import os
import tempfile
from datetime import datetime
import time
import json
from app.database.orm import get_db
from app.database.repositorios import RepositorioImportLog, RepositorioDatoImportado, RepositorioAuditoria
from app.importers import CSVImporter, ExcelImporter, TextImporter
from app.qr import QRGenerator
from app.security import get_current_user
from app.config import config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/import", tags=["Importación"])


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
        
        # Generar QR y preparar datos
        qr_gen = QRGenerator()
        registros_para_insertar = []
        registros_fallidos = 0
        
        for row in importer.data:
            try:
                # Generar QR con datos del registro
                qr_filename = f"qr_{importacion_id}_{len(registros_para_insertar)}.png"
                qr_filepath = qr_gen.generate_qr_from_data(row, qr_filename)
                
                # Preparar registro
                registro = {
                    "nombre": row.get("nombre") or row.get("Nombre") or "",
                    "email": row.get("email") or row.get("Email"),
                    "telefono": row.get("telefono") or row.get("Telefono"),
                    "empresa": row.get("empresa") or row.get("Empresa"),
                    "ciudad": row.get("ciudad") or row.get("Ciudad"),
                    "pais": row.get("pais") or row.get("Pais"),
                    "datos_adicionales": json.dumps({k: v for k, v in row.items() 
                                                    if k not in ["nombre", "email", "telefono", "empresa", "ciudad", "pais"]}),
                    "qr_filename": qr_filename,
                    "contenido_qr": json.dumps(row),
                    "creado_por": usuario_id,
                    "importacion_id": importacion_id,
                    "es_activo": True
                }
                registros_para_insertar.append(registro)
            except Exception as e:
                logger.error(f"Error procesando fila: {e}")
                registros_fallidos += 1
        
        # Insertar en lotes
        registros_importados = 0
        if registros_para_insertar:
            from app.models import DatoImportado
            
            # Insertar en lote
            for registro in registros_para_insertar:
                try:
                    from app.models import DatoImportado as Model
                    obj = Model(**registro)
                    db.add(obj)
                except Exception as e:
                    logger.error(f"Error insertando registro: {e}")
                    registros_fallidos += 1
            
            db.commit()
            registros_importados = len(registros_para_insertar) - registros_fallidos
        
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
    archivo: UploadFile = File(...),
    tabla: str = Form(...),
    delimitador: str = Form(default=","),
    background_tasks: BackgroundTasks = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None
):
    """Importar archivo CSV."""
    try:
        repo_import = RepositorioImportLog(db)
        
        # Guardar archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp_file:
            contenido = await archivo.read()
            tmp_file.write(contenido)
            temp_path = tmp_file.name
        
        # Crear log de importación
        log_data = {
            "archivo_nombre": archivo.filename,
            "archivo_tamanio": len(contenido),
            "tipo_archivo": "CSV",
            "tabla_destino": tabla,
            "delimitador": delimitador,
            "registros_totales": 0,
            "usuario_id": current_user["id"],
            "estado": "PENDING"
        }
        
        from app.schemas import ImportLogCrear
        log = repo_import.crear(ImportLogCrear(**log_data))
        
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
    archivo: UploadFile = File(...),
    tabla: str = Form(...),
    hoja: str = Form(default="0"),
    background_tasks: BackgroundTasks = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Importar archivo Excel."""
    try:
        repo_import = RepositorioImportLog(db)
        
        # Guardar archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_file:
            contenido = await archivo.read()
            tmp_file.write(contenido)
            temp_path = tmp_file.name
        
        # Crear log
        from app.schemas import ImportLogCrear
        log_data = {
            "archivo_nombre": archivo.filename,
            "archivo_tamanio": len(contenido),
            "tipo_archivo": "EXCEL",
            "tabla_destino": tabla,
            "registros_totales": 0,
            "usuario_id": current_user["id"],
            "estado": "PENDING"
        }
        
        log = repo_import.crear(ImportLogCrear(**log_data))
        
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
