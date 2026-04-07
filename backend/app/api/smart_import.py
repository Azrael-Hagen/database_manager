"""
Smart Import API – intelligent file analysis, preview, and execution.

Workflow for callers:
  1. POST /api/smart-import/analyze  → detect columns & suggest mappings
  2. POST /api/smart-import/preview  → show what changes would occur (no writes)
  3. POST /api/smart-import/execute  → commit the import with chosen mode
"""

from __future__ import annotations

import csv
import json
import logging
import uuid as _uuid
from datetime import datetime, timezone
from io import StringIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.database.orm import get_db
from app.importers.smart_importer import (
    apply_agent_row_changes,
    apply_line_plan,
    analyze_file,
    apply_mapping,
    find_existing_agent,
    preview_import,
)
from app.security import get_current_user, require_capture_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/smart-import", tags=["Importación Inteligente"])

_ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls", "txt", "dat"}
_MAX_FILE_BYTES = 20 * 1024 * 1024  # 20 MB
_DIRECT_FIELDS = {"nombre", "email", "telefono", "empresa", "ciudad", "pais"}


def _check_extension(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Extensión de archivo no permitida: .{ext}",
        )
    return ext


def _parse_rows(content: bytes, filename: str, delimiter: str) -> list[dict]:
    """Parse file content to a list of row dicts."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in ("xlsx", "xls"):
        import io
        import pandas as pd
        df = pd.read_excel(io.BytesIO(content), sheet_name=0)
        df = df.where(pd.notna(df), None)
        return df.to_dict(orient="records")
    else:
        text = content.decode("utf-8-sig", errors="replace")
        return list(csv.DictReader(StringIO(text), delimiter=delimiter))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/analyze")
async def analyze_import_file(
    archivo: UploadFile = File(...),
    delimitador: str = Form(","),
    current_user: dict = Depends(get_current_user),
):
    """
    Upload a file and receive:
    - Column detection with suggested canonical field mappings and confidence scores.
    - A 5-row data sample.
    - Total row count.

    Requires: capture role or higher.
    """
    require_capture_role(
        current_user,
        "Se requiere rol de captura o superior para usar importación inteligente.",
    )
    _check_extension(archivo.filename)

    content = await archivo.read()
    if len(content) > _MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Archivo demasiado grande (máximo 20 MB).",
        )

    result = analyze_file(content, archivo.filename, delimiter=delimitador)
    return {"status": "ok", "datos": result}


@router.post("/preview")
async def preview_import_file(
    archivo: UploadFile = File(...),
    delimitador: str = Form(","),
    mapeo: str = Form(
        ...,
        description='JSON: {"Columna Archivo": "campo_canonico", ...}',
    ),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Given a file and a confirmed column→canonical-field mapping, return a
    preview of the changes that would occur (no data is written).

    Each row is classified as:
    - **nuevo**       – would be inserted (no matching agent found)
    - **actualizar**  – would update an existing agent
    - **sin_cambio**  – existing agent has identical data (no write needed)

    Also indicates whether existing agents already have an active line number.

    Requires: capture role or higher.
    """
    require_capture_role(
        current_user,
        "Se requiere rol de captura o superior para usar importación inteligente.",
    )
    _check_extension(archivo.filename)

    try:
        mapping: dict = json.loads(mapeo)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El campo 'mapeo' debe ser un objeto JSON válido.",
        )
    if not isinstance(mapping, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El campo 'mapeo' debe ser un objeto JSON (dict).",
        )

    content = await archivo.read()
    if len(content) > _MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Archivo demasiado grande (máximo 20 MB).",
        )

    result = preview_import(
        content,
        archivo.filename,
        mapping,
        delimiter=delimitador,
        db=db,
    )
    return {"status": "ok", "datos": result}


@router.post("/execute")
async def execute_smart_import(
    archivo: UploadFile = File(...),
    delimitador: str = Form(","),
    mapeo: str = Form(
        ...,
        description='JSON: {"Columna Archivo": "campo_canonico", ...}',
    ),
    modo: str = Form(
        "insertar",
        description=(
            "insertar – only new records; "
            "actualizar – only update existing; "
            "insertar_o_actualizar – upsert"
        ),
    ),
    confirmacion: str = Form(
        "false",
        description="Debe ser 'true' para confirmar que se reviso el preview antes de aplicar.",
    ),
    modo_estricto_conflictos: str = Form(
        "false",
        description="Si es 'true', bloquea toda la ejecucion cuando el preview detecta conflictos de linea.",
    ),
    rollback_si_hay_errores: str = Form(
        "false",
        description="Si es 'true', revierte toda la transaccion cuando ocurre cualquier error por fila.",
    ),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Execute the smart import with the confirmed mapping.

    Modes:
    - **insertar**             – create only genuinely new agents (skip duplicates)
    - **actualizar**           – update only agents that already exist (skip unknowns)
    - **insertar_o_actualizar** – upsert: insert new, update existing

    Requires: capture role or higher.
    """
    require_capture_role(
        current_user,
        "Se requiere rol de captura o superior para usar importación inteligente.",
    )
    _check_extension(archivo.filename)

    VALID_MODES = {"insertar", "actualizar", "insertar_o_actualizar"}
    if modo not in VALID_MODES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Modo inválido: '{modo}'. Válidos: {sorted(VALID_MODES)}",
        )

    try:
        mapping: dict = json.loads(mapeo)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El campo 'mapeo' debe ser un objeto JSON válido.",
        )
    if not isinstance(mapping, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El campo 'mapeo' debe ser un objeto JSON (dict).",
        )

    content = await archivo.read()
    if len(content) > _MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Archivo demasiado grande (máximo 20 MB).",
        )

    if str(confirmacion).strip().lower() not in {"true", "1", "si", "sí", "yes"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ejecucion bloqueada: confirma primero en preview (confirmacion=true).",
        )

    strict_conflicts = str(modo_estricto_conflictos).strip().lower() in {"true", "1", "si", "sí", "yes"}
    rollback_on_error = str(rollback_si_hay_errores).strip().lower() in {"true", "1", "si", "sí", "yes"}

    all_rows = _parse_rows(content, archivo.filename, delimitador)

    if strict_conflicts:
        preview = preview_import(
            content,
            archivo.filename,
            mapping,
            delimiter=delimitador,
            db=db,
        )
        conflict_rows = [
            row for row in preview.get("filas_preview", [])
            if (row.get("plan_linea") or {}).get("accion") == "conflicto_linea_ocupada"
        ]
        if conflict_rows:
            conflict_detail = [
                {
                    "fila": row.get("fila"),
                    "linea": (row.get("plan_linea") or {}).get("numero"),
                    "agente_ocupante_id": (row.get("plan_linea") or {}).get("agente_ocupante_id"),
                }
                for row in conflict_rows[:10]
            ]
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "mensaje": "Modo estricto activo: existen conflictos de linea en preview.",
                    "conflictos": conflict_detail,
                    "total_conflictos": len(conflict_rows),
                },
            )

    from app.models import DatoImportado

    inserted = 0
    updated = 0
    skipped = 0
    errors: list[str] = []
    conflictos_linea = 0
    lineas_creadas = 0

    for idx, raw_row in enumerate(all_rows):
        mapped = apply_mapping(raw_row, mapping)
        if not mapped:
            skipped += 1
            continue

        try:
            existing = find_existing_agent(mapped, db)

            if existing and modo == "insertar":
                skipped += 1
                continue
            if not existing and modo == "actualizar":
                skipped += 1
                continue

            if existing and modo in {"actualizar", "insertar_o_actualizar"}:
                apply_agent_row_changes(existing, mapped, db)
                line_result = apply_line_plan(existing.id, mapped, db)
                if line_result.get("accion") == "conflicto_linea_ocupada":
                    conflictos_linea += 1
                    errors.append(
                        f"Fila {idx + 2}: conflicto de linea {line_result.get('numero')} ocupada por agente {line_result.get('agente_ocupante_id')}"
                    )
                if line_result.get("accion") == "crear_y_asignar":
                    lineas_creadas += 1
                updated += 1
            else:
                # Insert new agent
                direct = {k: v for k, v in mapped.items() if k in _DIRECT_FIELDS}
                extra = {k: v for k, v in mapped.items() if k not in _DIRECT_FIELDS}
                if not str(extra.get("alias") or "").strip() and str(direct.get("nombre") or "").strip():
                    extra["alias"] = str(direct.get("nombre") or "").strip()
                new_agent = DatoImportado(
                    uuid=str(_uuid.uuid4()),
                    nombre=direct.get("nombre", ""),
                    email=direct.get("email"),
                    telefono=direct.get("telefono"),
                    empresa=direct.get("empresa"),
                    ciudad=direct.get("ciudad"),
                    pais=direct.get("pais"),
                    datos_adicionales=(
                        json.dumps(extra, ensure_ascii=False) if extra else None
                    ),
                    creado_por=current_user["username"],
                    fecha_creacion=datetime.now(timezone.utc),
                    es_activo=True,
                )
                db.add(new_agent)
                db.flush()
                line_result = apply_line_plan(new_agent.id, mapped, db)
                if line_result.get("accion") == "conflicto_linea_ocupada":
                    conflictos_linea += 1
                    errors.append(
                        f"Fila {idx + 2}: conflicto de linea {line_result.get('numero')} ocupada por agente {line_result.get('agente_ocupante_id')}"
                    )
                if line_result.get("accion") == "crear_y_asignar":
                    lineas_creadas += 1
                inserted += 1

        except Exception as exc:
            logger.error("Error procesando fila %d: %s", idx + 2, exc)
            errors.append(f"Fila {idx + 2}: {exc}")

    if rollback_on_error and errors:
        db.rollback()
        return {
            "status": "ok",
            "datos": {
                "insertados": 0,
                "actualizados": 0,
                "omitidos": skipped,
                "conflictos_linea": conflictos_linea,
                "lineas_creadas": 0,
                "errores": errors,
                "rollback_aplicado": True,
                "insertados_revertidos": inserted,
                "actualizados_revertidos": updated,
            },
        }

    db.commit()
    logger.info(
        "smart-import ejecutado por %s: insertados=%d, actualizados=%d, omitidos=%d, errores=%d",
        current_user["username"],
        inserted,
        updated,
        skipped,
        len(errors),
    )

    return {
        "status": "ok",
        "datos": {
            "insertados": inserted,
            "actualizados": updated,
            "omitidos": skipped,
            "conflictos_linea": conflictos_linea,
            "lineas_creadas": lineas_creadas,
            "errores": errors,
            "rollback_aplicado": False,
        },
    }
