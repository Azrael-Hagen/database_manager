"""
Intelligent file importer: field detection, synonym mapping, agent-number check,
and import preview with change classification.
"""

from __future__ import annotations

import csv
import json
import logging
import re
from difflib import SequenceMatcher
from io import StringIO
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Field synonym catalog
# Keys = canonical field names (matching columns in datos_importados or the
# datos_adicionales JSON bag).
# Values = alternate header spellings accepted from uploaded files.
# ---------------------------------------------------------------------------
FIELD_SYNONYMS: dict[str, list[str]] = {
    "nombre": [
        "name", "full_name", "fullname", "nombre_completo", "agente",
        "agent", "nombres", "nom", "full name",
    ],
    "email": [
        "correo", "mail", "e_mail", "e-mail", "email_address",
        "correo_electronico", "correo electronico",
    ],
    "telefono": [
        "phone", "cel", "celular", "movil", "mobile", "teléfono", "tel",
        "telefono_movil", "phone_number", "celphone", "cellphone",
        "número", "numero",
    ],
    "empresa": [
        "company", "compania", "organización", "org", "organization",
        "compañia", "compañía",
    ],
    "ciudad": ["city", "localidad", "municipio"],
    "pais": ["country", "nación", "nacion", "pays", "país"],
    "alias": ["apodo", "nickname", "nick"],
    "ubicacion": ["ubicación", "location", "sede", "place", "ubicacion"],
    "fp": ["fecha_primera", "first_payment", "pago_inicial"],
    "fc": ["fecha_cobro", "billing_date", "cobro"],
    "grupo": ["group", "equipo", "team"],
    "numero_voip": [
        "voip", "numero_voip", "voip_number", "linea", "line",
        "extension", "ext", "numero_linea",
    ],
}

# Build inverse mapping: normalized_synonym → canonical
_SYNONYM_TO_CANONICAL: dict[str, str] = {}
for _canonical, _syns in FIELD_SYNONYMS.items():
    _SYNONYM_TO_CANONICAL[_canonical] = _canonical  # self-map
    for _s in _syns:
        _SYNONYM_TO_CANONICAL[re.sub(r"[\s\-]+", "_", _s.strip().lower())] = _canonical


def _normalize_header(h: str) -> str:
    """Lowercase, strip, replace spaces/hyphens with underscores."""
    return re.sub(r"[\s\-]+", "_", (h or "").strip().lower())


def _similarity(a: str, b: str) -> float:
    """SequenceMatcher ratio in [0, 1]."""
    return SequenceMatcher(None, a, b).ratio()


def suggest_mapping(header: str) -> dict:
    """
    Given a raw column header, suggest the canonical field mapping.

    Returns a dict with:
        header     – original header text
        normalized – normalized form used internally
        campo      – canonical field name, or None if unknown
        confianza  – float 0.0–1.0
        tipo       – "exacta" | "sinonimo" | "fuzzy" | "desconocido"
    """
    norm = _normalize_header(header)

    # 1 – Exact or synonym match
    if norm in _SYNONYM_TO_CANONICAL:
        canonical = _SYNONYM_TO_CANONICAL[norm]
        tipo = "exacta" if norm == canonical else "sinonimo"
        return {
            "header": header,
            "normalized": norm,
            "campo": canonical,
            "confianza": 1.0,
            "tipo": tipo,
        }

    # 2 – Fuzzy match against all known synonyms + canonical keys
    best_score = 0.0
    best_canonical: str | None = None
    for target, canonical in _SYNONYM_TO_CANONICAL.items():
        score = _similarity(norm, target)
        if score > best_score:
            best_score = score
            best_canonical = canonical

    if best_score >= 0.75:
        return {
            "header": header,
            "normalized": norm,
            "campo": best_canonical,
            "confianza": round(best_score, 3),
            "tipo": "fuzzy",
        }

    # 3 – Unknown
    return {
        "header": header,
        "normalized": norm,
        "campo": None,
        "confianza": 0.0,
        "tipo": "desconocido",
    }


# ---------------------------------------------------------------------------
# File parsing helpers
# ---------------------------------------------------------------------------

def _parse_file_to_rows(content: bytes, filename: str, delimiter: str = ",") -> tuple[list[dict], list[str]]:
    """
    Parse file bytes into a list of row dicts.
    Returns (rows, errors).
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    rows: list[dict] = []
    errors: list[str] = []

    try:
        if ext in ("xlsx", "xls"):
            import io
            import pandas as pd
            df = pd.read_excel(io.BytesIO(content), sheet_name=0)
            df = df.where(pd.notna(df), None)
            rows = df.to_dict(orient="records")
        else:
            # CSV / TXT / DAT – treat as delimited text
            text = content.decode("utf-8-sig", errors="replace")
            reader = csv.DictReader(StringIO(text), delimiter=delimiter)
            for row in reader:
                rows.append(dict(row))
    except Exception as exc:
        errors.append(f"Error al parsear '{filename}': {exc}")

    return rows, errors


# ---------------------------------------------------------------------------
# Public API: analyze
# ---------------------------------------------------------------------------

def analyze_file(
    content: bytes,
    filename: str,
    delimiter: str = ",",
) -> dict:
    """
    Parse a file and return column analysis + sample rows.

    Returns:
        columnas_detectadas – list of suggest_mapping() results for each header
        total_filas         – total data rows (excluding header)
        muestra             – first 5 rows as list[dict[str, str]]
        errores             – parse errors, if any
    """
    rows, errors = _parse_file_to_rows(content, filename, delimiter)

    if errors or not rows:
        if not errors:
            errors.append("El archivo no contiene filas de datos.")
        return {
            "columnas_detectadas": [],
            "total_filas": 0,
            "muestra": [],
            "errores": errors,
        }

    headers = list(rows[0].keys())
    suggestions = [suggest_mapping(h) for h in headers]

    # Serialize sample (first 5 rows) to plain strings
    muestra = [
        {k: ("" if v is None else str(v)) for k, v in row.items()}
        for row in rows[:5]
    ]

    return {
        "columnas_detectadas": suggestions,
        "total_filas": len(rows),
        "muestra": muestra,
        "errores": errors,
    }


# ---------------------------------------------------------------------------
# Agent number / line status helpers
# ---------------------------------------------------------------------------

def agent_has_active_line(agent_id: int, db: Any) -> bool:
    """Return True if the agent has at least one active line assignment."""
    from app.models import AgenteLineaAsignacion

    return (
        db.query(AgenteLineaAsignacion)
        .filter(
            AgenteLineaAsignacion.agente_id == agent_id,
            AgenteLineaAsignacion.es_activa.is_(True),
        )
        .first()
        is not None
    )


def agent_has_voip_number(agent_id: int, db: Any) -> bool:
    """Return True if the agent has a non-empty numero_voip in any payment row."""
    from app.models import PagoSemanal

    return (
        db.query(PagoSemanal)
        .filter(
            PagoSemanal.agente_id == agent_id,
            PagoSemanal.numero_voip.isnot(None),
            PagoSemanal.numero_voip != "",
        )
        .first()
        is not None
    )


def get_agent_number_status(agent_id: int, db: Any) -> dict:
    """
    Describe the phone/line status of an agent.

    Returns:
        tiene_linea_activa – bool
        tiene_numero_voip  – bool
        necesita_numero    – True when the agent has neither
    """
    tiene_linea = agent_has_active_line(agent_id, db)
    tiene_voip = agent_has_voip_number(agent_id, db)
    return {
        "tiene_linea_activa": tiene_linea,
        "tiene_numero_voip": tiene_voip,
        "necesita_numero": not tiene_linea and not tiene_voip,
    }


# ---------------------------------------------------------------------------
# Mapping application
# ---------------------------------------------------------------------------

def apply_mapping(raw_row: dict, mapping: dict[str, str]) -> dict:
    """
    Project a raw file row through a user-confirmed column→field mapping.

    mapping: {column_header: canonical_field | ""}
             Empty string means "ignore this column".

    Returns a dict of {canonical_field: value_str} for non-empty values.
    """
    result: dict[str, str] = {}
    for header, canonical in mapping.items():
        if not canonical:
            continue  # user chose to ignore this column
        value = raw_row.get(header)
        if value is not None and str(value).strip():
            result[canonical] = str(value).strip()
    return result


# ---------------------------------------------------------------------------
# Duplicate / existing-agent lookup
# ---------------------------------------------------------------------------

_MATCH_PRIORITY = ["email", "telefono"]  # dedup priority order


def find_existing_agent(mapped_row: dict, db: Any):
    """
    Try to find an existing DatoImportado matching the row by email or telefono.
    Returns the instance or None.
    """
    from app.models import DatoImportado

    for field in _MATCH_PRIORITY:
        value = mapped_row.get(field)
        if value:
            agent = (
                db.query(DatoImportado)
                .filter(getattr(DatoImportado, field) == str(value))
                .first()
            )
            if agent:
                return agent
    return None


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------

_UPDATABLE_FIELDS = {"nombre", "email", "telefono", "empresa", "ciudad", "pais"}


def preview_import(
    content: bytes,
    filename: str,
    mapping: dict[str, str],
    delimiter: str = ",",
    db: Any | None = None,
) -> dict:
    """
    Simulate an import and classify each row as new / update / no-change / error.

    Returns:
        nuevos           – count of rows that would be inserted
        actualizaciones  – count of rows that would update an existing agent
        sin_cambios      – count of rows where the agent already has identical data
        filas_preview    – list of per-row classification dicts:
                           {fila, accion, datos_mapeados,
                            agente_existente_id, tiene_numero}
        errores_formato  – rows that could not be mapped at all
    """
    rows, parse_errors = _parse_file_to_rows(content, filename, delimiter)

    if parse_errors and not rows:
        return {
            "nuevos": 0,
            "actualizaciones": 0,
            "sin_cambios": 0,
            "filas_preview": [],
            "errores_formato": parse_errors,
        }

    nuevos = 0
    actualizaciones = 0
    sin_cambios = 0
    filas_preview: list[dict] = []
    formato_errors: list[str] = []

    for idx, raw_row in enumerate(rows):
        mapped = apply_mapping(raw_row, mapping)

        if not mapped:
            formato_errors.append(
                f"Fila {idx + 2}: sin campos válidos después del mapeo."
            )
            continue

        accion = "nuevo"
        agente_id = None
        tiene_numero: bool | None = None

        if db is not None:
            existing = find_existing_agent(mapped, db)
            if existing:
                agente_id = existing.id
                # Compare updatable fields to detect actual changes
                changed_fields = {
                    f: mapped[f]
                    for f in mapped
                    if f in _UPDATABLE_FIELDS
                    and str(getattr(existing, f, "") or "") != mapped[f]
                }
                if changed_fields:
                    accion = "actualizar"
                    actualizaciones += 1
                else:
                    accion = "sin_cambio"
                    sin_cambios += 1
                tiene_numero = agent_has_active_line(existing.id, db)
            else:
                nuevos += 1
        else:
            nuevos += 1

        filas_preview.append(
            {
                "fila": idx + 2,
                "accion": accion,
                "datos_mapeados": mapped,
                "agente_existente_id": agente_id,
                "tiene_numero": tiene_numero,
            }
        )

    return {
        "nuevos": nuevos,
        "actualizaciones": actualizaciones,
        "sin_cambios": sin_cambios,
        "filas_preview": filas_preview,
        "errores_formato": formato_errors,
    }
