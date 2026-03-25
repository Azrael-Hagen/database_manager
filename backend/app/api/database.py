"""Endpoints para gestión de bases de datos."""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body, UploadFile, File, Form, Request
from sqlalchemy import text, inspect
from sqlalchemy.orm import Session
from app.database.orm import get_db
from app.database import orm as orm_schema
from app.security import get_current_user, require_admin_role, require_capture_role, require_server_machine_request
from app.utils.agent_cleanup import cleanup_redundant_agents
import logging
import json
import csv
import io
import os
import re

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/databases", tags=["Database Management"])

TEMP_OBJECT_PREFIXES = ("tmp_", "temp_", "test_", "ui_temp_", "debug_", "backup_tmp_")


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
    order_by: str | None = Query(None),
    direction: str = Query("asc"),
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

        direction_value = (direction or "asc").strip().lower()
        direction_sql = "DESC" if direction_value == "desc" else "ASC"
        safe_order = order_by if order_by in columns else None
        order_sql = f" ORDER BY `{safe_order}` {direction_sql}" if safe_order else ""
        
        # Obtener datos
        result = db.execute(text(f"SELECT * FROM `{table_name}`{order_sql} LIMIT {limit} OFFSET {offset}"))
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
            "offset": offset,
            "order_by": safe_order,
            "direction": direction_sql.lower(),
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
    require_admin_role(current_user, "Solo administradores pueden ejecutar consultas SQL personalizadas")
    try:
        sql_query = query or (payload or {}).get("query")
        if not sql_query or not str(sql_query).strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debe enviar una consulta SQL"
            )

        is_select = str(sql_query).strip().upper().startswith("SELECT")

        logger.info(f"Usuario {current_user['username']} ejecutando query en BD {db_name}: {str(sql_query)[:100]}...")
        
        # Cambiar a la base de datos
        db.execute(text(f"USE `{db_name}`"))
        
        # Ejecutar la consulta
        result = db.execute(text(sql_query))
        
        # Si es SELECT, devolver resultados
        if is_select:
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
    except HTTPException:
        db.rollback()
        raise
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
    require_admin_role(current_user, "Solo administradores pueden crear tablas")
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
    require_admin_role(current_user, "Solo administradores pueden eliminar tablas")
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
    require_capture_role(current_user)
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
    require_admin_role(current_user, "Solo administradores pueden eliminar bases de datos")

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
    require_admin_role(current_user, "Solo administradores pueden crear vistas")
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
    require_admin_role(current_user, "Solo administradores pueden eliminar vistas")
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


@router.get("/{db_name}/maintenance/overview")
async def maintenance_overview(
    db_name: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Resumen de depuración de tablas y vistas para administradores."""
    db_name = _safe_ident(db_name, "Base de datos")
    require_admin_role(current_user, "Solo administradores pueden depurar el esquema")
    db.execute(text(f"USE `{db_name}`"))

    objects = db.execute(
        text(
            """
            SELECT table_name, table_type
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
            ORDER BY table_type, table_name
            """
        )
    ).mappings().all()
    protected = {
        "usuarios", "agentes_operativos", "import_logs", "auditoria_acciones", "config_sistema",
        "pagos_semanales", "lineas_telefonicas", "agente_linea_asignaciones", "alertas_pago", "recibos_pago",
        "ladas_catalogo", "agente_lada_preferencias", "esquemas_base_datos"
    }
    recommendations = []
    rows = []
    for item in objects:
        name = item["table_name"]
        table_type = item["table_type"]
        row_count = None
        if table_type == "BASE TABLE":
            try:
                row_count = int(db.execute(text(f"SELECT COUNT(*) FROM `{name}`")).scalar() or 0)
            except Exception:
                row_count = None
        is_temp = name.lower().startswith(TEMP_OBJECT_PREFIXES)
        is_protected = name in protected or name.startswith("vw_")
        rows.append({
            "name": name,
            "type": table_type,
            "row_count": row_count,
            "is_protected": is_protected,
            "is_temp_candidate": bool(is_temp),
        })
        if is_temp and not is_protected:
            recommendations.append(f"Eliminar objeto temporal: {name}")

    useful_views = ["vw_agentes_qr_estado", "vw_usuarios_roles", "vw_pagos_pendientes", "vw_agentes_extensiones_pago_actual"]
    return {
        "status": "success",
        "database": db_name,
        "objects": rows,
        "recommended_actions": recommendations,
        "useful_views_expected": useful_views,
    }


@router.post("/{db_name}/maintenance/useful-views")
async def create_useful_views(
    db_name: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Crear o refrescar vistas operativas utiles."""
    db_name = _safe_ident(db_name, "Base de datos")
    require_admin_role(current_user, "Solo administradores pueden crear vistas útiles")
    try:
        db.execute(text(f"USE `{db_name}`"))
        statements = orm_schema.get_useful_views_sql_map(db.connection())
        created = []
        for name, sql in statements.items():
            db.execute(text(sql))
            created.append(name)
        db.commit()
        return {"status": "success", "database": db_name, "views": created, "message": "Vistas útiles creadas/actualizadas"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Error creando vistas útiles: {str(e)}")


@router.post("/{db_name}/maintenance/purge-temporary")
async def purge_temporary_objects(
    db_name: str,
    request: Request,
    include_empty: bool = Query(False),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Eliminar tablas y vistas temporales o de prueba detectadas de forma segura."""
    db_name = _safe_ident(db_name, "Base de datos")
    require_admin_role(current_user, "Solo administradores pueden depurar tablas y vistas")
    require_server_machine_request(request)
    db.execute(text(f"USE `{db_name}`"))
    objects = db.execute(
        text(
            """
            SELECT table_name, table_type
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
            ORDER BY table_type, table_name
            """
        )
    ).mappings().all()

    dropped = []
    for item in objects:
        name = item["table_name"]
        table_type = item["table_type"]
        lower_name = name.lower()
        should_drop = lower_name.startswith(TEMP_OBJECT_PREFIXES)
        if include_empty and table_type == "BASE TABLE" and not should_drop:
            row_count = int(db.execute(text(f"SELECT COUNT(*) FROM `{name}`")).scalar() or 0)
            should_drop = row_count == 0 and lower_name not in {
                "usuarios", "agentes_operativos", "import_logs", "auditoria_acciones", "config_sistema",
                "pagos_semanales", "lineas_telefonicas", "agente_linea_asignaciones", "alertas_pago", "recibos_pago",
                "ladas_catalogo", "agente_lada_preferencias", "esquemas_base_datos"
            }
        if not should_drop:
            continue
        if table_type == "VIEW":
            db.execute(text(f"DROP VIEW `{name}`"))
        else:
            db.execute(text(f"DROP TABLE `{name}`"))
        dropped.append(name)

    db.commit()
    return {"status": "success", "database": db_name, "dropped": dropped, "message": f"Se eliminaron {len(dropped)} objetos temporales"}


@router.post("/{db_name}/maintenance/cleanup-redundant-agents")
async def cleanup_redundant_agents_maintenance(
    db_name: str,
    request: Request,
    dry_run: bool = Query(False, description="Si es true, solo analiza y no elimina"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Depuración segura de agentes test/duplicados sin referencias operativas."""
    db_name = _safe_ident(db_name, "Base de datos")
    require_admin_role(current_user, "Solo administradores pueden depurar agentes")
    require_server_machine_request(request)

    if db_name != "database_manager":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta depuración solo aplica sobre database_manager",
        )

    db.execute(text("USE `database_manager`"))
    try:
        result = cleanup_redundant_agents(db, apply_changes=not dry_run, sync_legacy=True)
        if dry_run:
            db.rollback()
            return {
                "status": "success",
                "database": db_name,
                "dry_run": True,
                "message": "Análisis completado. No se aplicaron cambios.",
                "data": result,
            }

        db.commit()
        return {
            "status": "success",
            "database": db_name,
            "dry_run": False,
            "message": f"Depuración completada. Eliminados: {result.get('deleted', 0)}",
            "data": result,
        }
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error depurando agentes redundantes: {str(exc)}",
        )