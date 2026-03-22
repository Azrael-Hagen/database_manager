"""Endpoints para gestión de bases de datos."""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body, UploadFile, File, Form
from sqlalchemy import text, inspect
from sqlalchemy.orm import Session
from app.database.orm import get_db
from app.security import get_current_user
import logging
import json
import csv
import io
import os
import re

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/databases", tags=["Database Management"])


def _safe_ident(name: str, field: str = "identificador") -> str:
    """Validar nombres de BD/tabla/vista para evitar inyecciones por identificador."""
    value = (name or "").strip()
    if not value or not re.match(r"^[a-zA-Z0-9_]+$", value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field} inválido"
        )
    return value


@router.get("/")
async def list_databases(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Listar todas las bases de datos disponibles."""
    try:
        logger.info(f"Usuario {current_user['username']} listando bases de datos")
        result = db.execute(text("SHOW DATABASES"))
        databases = [row[0] for row in result.fetchall()]
        logger.info(f"Encontradas {len(databases)} bases de datos")
        return {
            "status": "success",
            "data": databases
        }
    except Exception as e:
        logger.error(f"Error listando bases de datos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listando bases de datos: {str(e)}"
        )


@router.get("/{db_name}/tables")
async def list_tables(
    db_name: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Listar tablas en una base de datos específica."""
    db_name = _safe_ident(db_name, "Base de datos")
    try:
        logger.info(f"Usuario {current_user['username']} listando tablas en BD: {db_name}")
        # Cambiar a la base de datos especificada
        db.execute(text(f"USE `{db_name}`"))
        result = db.execute(text("SHOW TABLES"))
        tables = [row[0] for row in result.fetchall()]
        logger.info(f"Encontradas {len(tables)} tablas en {db_name}")
        return {
            "status": "success",
            "database": db_name,
            "data": tables
        }
    except Exception as e:
        logger.error(f"Error listando tablas en {db_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listando tablas: {str(e)}"
        )


@router.get("/{db_name}/tables/{table_name}")
async def get_table_data(
    db_name: str,
    table_name: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener datos de una tabla específica."""
    db_name = _safe_ident(db_name, "Base de datos")
    table_name = _safe_ident(table_name, "Tabla o vista")
    try:
        logger.info(f"Usuario {current_user['username']} consultando tabla {table_name} en BD {db_name}")
        # Cambiar a la base de datos
        db.execute(text(f"USE `{db_name}`"))
        
        # Obtener estructura de la tabla
        result = db.execute(text(f"DESCRIBE `{table_name}`"))
        columns = [row[0] for row in result.fetchall()]
        
        # Obtener datos
        result = db.execute(text(f"SELECT * FROM `{table_name}` LIMIT {limit} OFFSET {offset}"))
        rows = [dict(zip(columns, row)) for row in result.fetchall()]
        
        # Contar total de registros
        count_result = db.execute(text(f"SELECT COUNT(*) FROM `{table_name}`"))
        total = count_result.fetchone()[0]
        
        logger.info(f"Tabla {table_name}: {len(rows)} registros mostrados de {total} total")
        return {
            "status": "success",
            "database": db_name,
            "table": table_name,
            "columns": columns,
            "data": rows,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Error obteniendo datos de tabla {table_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo datos: {str(e)}"
        )


@router.post("/{db_name}/query")
async def execute_query(
    db_name: str,
    query: str = Query(None, description="Consulta SQL a ejecutar"),
    payload: dict = Body(default=None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Ejecutar una consulta SQL personalizada."""
    db_name = _safe_ident(db_name, "Base de datos")
    try:
        sql_query = query or (payload or {}).get("query")
        if not sql_query or not str(sql_query).strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debe enviar una consulta SQL"
            )

        logger.info(f"Usuario {current_user['username']} ejecutando query en BD {db_name}: {str(sql_query)[:100]}...")
        
        # Cambiar a la base de datos
        db.execute(text(f"USE `{db_name}`"))
        
        # Ejecutar la consulta
        result = db.execute(text(sql_query))
        
        # Si es SELECT, devolver resultados
        if sql_query.strip().upper().startswith("SELECT"):
            columns = result.keys()
            rows = [dict(zip(columns, row)) for row in result.fetchall()]
            logger.info(f"Query SELECT ejecutada, {len(rows)} filas retornadas")
            return {
                "status": "success",
                "database": db_name,
                "query": sql_query,
                "data": rows,
                "row_count": len(rows)
            }
        else:
            # Para INSERT, UPDATE, DELETE, etc.
            db.commit()
            logger.info(f"Query no-SELECT ejecutada: {sql_query}")
            return {
                "status": "success",
                "database": db_name,
                "query": sql_query,
                "message": "Query ejecutada exitosamente"
            }
    except Exception as e:
        logger.error(f"Error ejecutando query: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error ejecutando query: {str(e)}"
        )


@router.post("/{db_name}/tables")
async def create_table(
    db_name: str,
    table_name: str = Query(..., description="Nombre de la tabla"),
    schema_sql: str = Query(..., description="SQL para crear la tabla, ej: CREATE TABLE ..."),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Crear una nueva tabla."""
    db_name = _safe_ident(db_name, "Base de datos")
    table_name = _safe_ident(table_name, "Tabla")
    try:
        logger.info(f"Usuario {current_user['username']} creando tabla {table_name} en BD {db_name}")
        
        # Cambiar a la base de datos
        db.execute(text(f"USE `{db_name}`"))
        
        # Ejecutar CREATE TABLE
        db.execute(text(schema_sql))
        db.commit()
        
        logger.info(f"Tabla {table_name} creada exitosamente")
        return {
            "status": "success",
            "database": db_name,
            "table": table_name,
            "message": "Tabla creada exitosamente"
        }
    except Exception as e:
        logger.error(f"Error creando tabla {table_name}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creando tabla: {str(e)}"
        )


@router.delete("/{db_name}/tables/{table_name}")
async def drop_table(
    db_name: str,
    table_name: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Eliminar una tabla."""
    db_name = _safe_ident(db_name, "Base de datos")
    table_name = _safe_ident(table_name, "Tabla")
    try:
        logger.info(f"Usuario {current_user['username']} eliminando tabla {table_name} en BD {db_name}")
        
        # Cambiar a la base de datos
        db.execute(text(f"USE `{db_name}`"))
        
        # Ejecutar DROP TABLE
        db.execute(text(f"DROP TABLE `{table_name}`"))
        db.commit()
        
        logger.info(f"Tabla {table_name} eliminada exitosamente")
        return {
            "status": "success",
            "database": db_name,
            "table": table_name,
            "message": "Tabla eliminada exitosamente"
        }
    except Exception as e:
        logger.error(f"Error eliminando tabla {table_name}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error eliminando tabla: {str(e)}"
        )


def _safe_col(name: str) -> str:
    """Sanitizar nombre de columna para uso como identificador SQL."""
    cleaned = re.sub(r'[^a-zA-Z0-9_]', '_', (name or '').strip())
    return cleaned or 'col'


@router.post("/{db_name}/import")
async def import_file_to_database(
    db_name: str,
    file: UploadFile = File(...),
    table_name: str = Form(...),
    delimiter: str = Form(","),
    encoding: str = Form("utf-8"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Importar CSV/TXT/DAT/TSV a una tabla en la base de datos indicada."""
    # Validate file extension
    fname = file.filename or ''
    ext = os.path.splitext(fname.lower())[1]
    if ext not in {'.csv', '.txt', '.dat', '.tsv'}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de archivo no soportado: {ext or 'sin extensión'}. Use CSV, TXT, DAT o TSV."
        )

    # Validate identifiers (no backticks allowed)
    if '`' in db_name or '`' in table_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nombre inválido")
    safe_table = re.sub(r'[^a-zA-Z0-9_]', '_', table_name.strip())
    if not safe_table:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nombre de tabla inválido")

    try:
        content = await file.read()

        # Decode with fallback
        actual_encoding = 'utf-8-sig' if encoding == 'utf-8' else encoding
        try:
            text_content = content.decode(actual_encoding)
        except UnicodeDecodeError:
            text_content = content.decode('latin-1')

        # Handle escaped tab delimiter from HTML form value
        actual_delimiter = '\t' if delimiter in ('\\t', '\t') else (delimiter or ',')

        reader = csv.DictReader(io.StringIO(text_content), delimiter=actual_delimiter)
        rows = list(reader)

        if not rows:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo está vacío o no tiene encabezados"
            )

        # Build column mapping: original header → safe SQL identifier
        raw_cols = list(rows[0].keys())
        col_map = {}
        seen = set()
        for col in raw_cols:
            safe = _safe_col(col)
            # Deduplicate
            base, n = safe, 1
            while safe in seen:
                safe = f"{base}_{n}"
                n += 1
            col_map[col] = safe
            seen.add(safe)

        safe_cols = list(col_map.values())

        # Switch to the target database
        db.execute(text(f"USE `{db_name}`"))

        # Create table if it doesn't exist, or add missing columns
        exists = db.execute(
            text("SELECT COUNT(*) FROM information_schema.tables "
                 "WHERE table_schema = DATABASE() AND table_name = :t"),
            {"t": safe_table}
        ).scalar()

        if not exists:
            create_parts = ["`id` INT AUTO_INCREMENT PRIMARY KEY",
                            "`_imported_at` DATETIME DEFAULT CURRENT_TIMESTAMP"]
            create_parts.extend([f"`{c}` TEXT NULL" for c in safe_cols])
            db.execute(text(f"CREATE TABLE `{safe_table}` ({', '.join(create_parts)}) ENGINE=InnoDB"))
            db.commit()
        else:
            current_cols = {row[0] for row in
                            db.execute(text(f"SHOW COLUMNS FROM `{safe_table}`")).fetchall()}
            for c in safe_cols:
                if c not in current_cols:
                    db.execute(text(f"ALTER TABLE `{safe_table}` ADD COLUMN `{c}` TEXT NULL"))
            db.commit()

        # Insert rows
        cols_sql = ", ".join([f"`{c}`" for c in safe_cols])
        vals_sql = ", ".join([f":{c}" for c in safe_cols])
        stmt = text(f"INSERT INTO `{safe_table}` ({cols_sql}) VALUES ({vals_sql})")

        ok = failed = 0
        for row in rows:
            payload = {}
            for orig, safe in col_map.items():
                v = row.get(orig)
                payload[safe] = str(v) if v is not None else None
            try:
                db.execute(stmt, payload)
                ok += 1
            except Exception:
                failed += 1
        db.commit()

        logger.info(f"Usuario {current_user['username']} importó {ok} filas a {db_name}.{safe_table}")
        return {
            "status": "success",
            "database": db_name,
            "table": safe_table,
            "imported": ok,
            "failed": failed,
            "total": len(rows)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importando archivo a {db_name}.{safe_table}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al importar: {str(e)}"
        )


_PROTECTED_DATABASES = {'information_schema', 'mysql', 'performance_schema', 'sys'}


@router.delete("/{db_name}")
async def drop_database(
    db_name: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Eliminar una base de datos completa (solo administradores)."""
    db_name = _safe_ident(db_name, "Base de datos")
    if not current_user.get('es_admin', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores pueden eliminar bases de datos"
        )

    from app.config import config as app_config
    if db_name.lower() in _PROTECTED_DATABASES or db_name == app_config.DB_NAME:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede eliminar la base de datos '{db_name}'"
        )

    if '`' in db_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nombre inválido")

    try:
        logger.warning(f"Usuario {current_user['username']} eliminando base de datos: {db_name}")
        db.execute(text(f"DROP DATABASE `{db_name}`"))
        db.commit()
        logger.warning(f"Base de datos eliminada: {db_name}")
        return {"status": "success", "message": f"Base de datos '{db_name}' eliminada"}
    except Exception as e:
        logger.error(f"Error eliminando base de datos {db_name}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error eliminando base de datos: {str(e)}"
        )


@router.get("/{db_name}/views")
async def list_views(
    db_name: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Listar vistas de una base de datos específica."""
    db_name = _safe_ident(db_name, "Base de datos")
    try:
        logger.info(f"Usuario {current_user['username']} listando vistas en BD: {db_name}")
        db.execute(text(f"USE `{db_name}`"))
        result = db.execute(text("SHOW FULL TABLES WHERE Table_type = 'VIEW'"))
        views = [row[0] for row in result.fetchall()]
        return {
            "status": "success",
            "database": db_name,
            "data": views
        }
    except Exception as e:
        logger.error(f"Error listando vistas en {db_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listando vistas: {str(e)}"
        )


@router.post("/{db_name}/views")
async def create_view(
    db_name: str,
    payload: dict = Body(...),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Crear una vista SQL (temporal de trabajo) en la BD indicada."""
    db_name = _safe_ident(db_name, "Base de datos")
    view_name = _safe_ident((payload or {}).get("view_name", ""), "Vista")
    select_query = str((payload or {}).get("select_query", "")).strip()
    or_replace = bool((payload or {}).get("or_replace", True))

    if not select_query:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debe enviar select_query")

    if not select_query.upper().startswith("SELECT"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La vista debe crearse a partir de un SELECT")

    try:
        db.execute(text(f"USE `{db_name}`"))
        prefix = "CREATE OR REPLACE VIEW" if or_replace else "CREATE VIEW"
        db.execute(text(f"{prefix} `{view_name}` AS {select_query}"))
        db.commit()
        logger.info(f"Usuario {current_user['username']} creó vista {db_name}.{view_name}")
        return {
            "status": "success",
            "database": db_name,
            "view": view_name,
            "message": "Vista creada exitosamente"
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error creando vista {db_name}.{view_name}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Error creando vista: {str(e)}")


@router.delete("/{db_name}/views/{view_name}")
async def drop_view(
    db_name: str,
    view_name: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Eliminar una vista de una base de datos específica."""
    db_name = _safe_ident(db_name, "Base de datos")
    view_name = _safe_ident(view_name, "Vista")
    try:
        db.execute(text(f"USE `{db_name}`"))
        db.execute(text(f"DROP VIEW `{view_name}`"))
        db.commit()
        logger.info(f"Usuario {current_user['username']} eliminó vista {db_name}.{view_name}")
        return {
            "status": "success",
            "database": db_name,
            "view": view_name,
            "message": "Vista eliminada exitosamente"
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error eliminando vista {db_name}.{view_name}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Error eliminando vista: {str(e)}")