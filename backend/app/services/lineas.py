"""Helpers reutilizables para normalizacion y serializacion de lineas."""

from datetime import date, datetime
import re

from fastapi import HTTPException, status


LINEA_CATEGORIAS_VALIDAS = {"FIJO", "MOVIL", "NO_DEFINIDA"}
LINEA_ESTADOS_CONEXION_VALIDOS = {"CONECTADA", "DESCONECTADA", "DESCONOCIDA"}


def normalize_lada(raw: str) -> str:
    value = re.sub(r"\D", "", str(raw or "").strip())
    if len(value) < 2 or len(value) > 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lada invalida")
    return value


def normalize_categoria_linea(raw_value, default: str = "NO_DEFINIDA") -> str:
    value = str(raw_value or "").strip().upper()
    if not value:
        return default
    if value not in LINEA_CATEGORIAS_VALIDAS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="categoria_linea invalida. Valores: FIJO, MOVIL, NO_DEFINIDA",
        )
    return value


def normalize_estado_conexion(raw_value, default: str = "DESCONOCIDA") -> str:
    value = str(raw_value or "").strip().upper()
    if not value:
        return default
    if value not in LINEA_ESTADOS_CONEXION_VALIDOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="estado_conexion invalido. Valores: CONECTADA, DESCONECTADA, DESCONOCIDA",
        )
    return value


def parse_fecha_ultimo_uso(raw_value):
    if raw_value in (None, ""):
        return None
    if isinstance(raw_value, datetime):
        return raw_value
    raw = str(raw_value).strip()
    if not raw:
        return None
    try:
        if len(raw) == 10:
            return datetime.combine(date.fromisoformat(raw), datetime.min.time())
        return datetime.fromisoformat(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="fecha_ultimo_uso invalida. Usa ISO (AAAA-MM-DD o AAAA-MM-DDTHH:MM:SS)",
        ) from exc


def extract_lada_from_number(number: str, known_codes: list[str]) -> str | None:
    digits = re.sub(r"\D", "", str(number or ""))
    if not digits:
        return None
    for code in sorted((value for value in known_codes if value), key=len, reverse=True):
        if digits.startswith(code):
            return code
    return digits[:3] if len(digits) >= 3 else digits


def serialize_linea_operativa(linea, *, assignment=None, known_codes: list[str] | None = None, synced_prefix: str = "SYNC extensions_pbx") -> dict:
    known_codes = known_codes or []
    resolved_lada = extract_lada_from_number(getattr(linea, "numero", ""), known_codes)
    agente = getattr(assignment, "agente", None) if assignment else None
    ocupada = assignment is not None
    return {
        "id": linea.id,
        "numero": linea.numero,
        "tipo": linea.tipo,
        "descripcion": linea.descripcion,
        "categoria_linea": normalize_categoria_linea(getattr(linea, "categoria_linea", None), default="NO_DEFINIDA"),
        "estado_conexion": normalize_estado_conexion(getattr(linea, "estado_conexion", None), default="DESCONOCIDA"),
        "fecha_ultimo_uso": linea.fecha_ultimo_uso.isoformat() if getattr(linea, "fecha_ultimo_uso", None) else None,
        "origen": "PBX" if str(getattr(linea, "descripcion", "") or "").startswith(synced_prefix) else "MANUAL",
        "lada": resolved_lada,
        "ocupada": ocupada,
        "agente": {
            "id": agente.id,
            "nombre": agente.nombre,
            "telefono": agente.telefono,
        } if agente else None,
        "fecha_asignacion": assignment.fecha_asignacion.isoformat() if assignment and getattr(assignment, "fecha_asignacion", None) else None,
    }


def build_empty_line_sync_result() -> dict[str, int]:
    return {
        "source": 0,
        "created": 0,
        "updated": 0,
        "deactivated": 0,
        "ladas_created": 0,
        "ladas_reactivated": 0,
    }
