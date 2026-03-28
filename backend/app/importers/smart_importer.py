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
        "num_ext", "numext", "num ext", "num. ext",
    ],
}

# Build inverse mapping: normalized_synonym → canonical
_SYNONYM_TO_CANONICAL: dict[str, str] = {}
for _canonical, _syns in FIELD_SYNONYMS.items():
    _SYNONYM_TO_CANONICAL[_canonical] = _canonical  # self-map
    for _s in _syns:
        _normalized_syn = re.sub(r"[\s\-]+", "_", _s.strip().lower())
        _normalized_syn = re.sub(r"[^a-z0-9_]+", "", _normalized_syn)
        _SYNONYM_TO_CANONICAL[_normalized_syn] = _canonical


def _normalize_header(h: str) -> str:
    """Lowercase, strip, replace spaces/hyphens with underscores."""
    normalized = re.sub(r"[\s\-]+", "_", (h or "").strip().lower())
    normalized = re.sub(r"[^a-z0-9_]+", "", normalized)
    return normalized


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


def _safe_json_dict(raw: str | None) -> dict:
    try:
        parsed = json.loads(raw or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _extract_alias_from_agent(agent: Any) -> str:
    extras = _safe_json_dict(getattr(agent, "datos_adicionales", None))
    return str(extras.get("alias") or "").strip()


def _extract_voip_from_agent(agent: Any) -> str:
    extras = _safe_json_dict(getattr(agent, "datos_adicionales", None))
    return str(extras.get("numero_voip") or "").strip()


def _normalized_cmp(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _find_agent_by_alias_scan(alias: str, db: Any):
    from app.models import DatoImportado

    target = _normalized_cmp(alias)
    if not target:
        return None

    candidates = (
        db.query(DatoImportado)
        .filter(DatoImportado.es_activo.is_(True))
        .all()
    )
    for candidate in candidates:
        if _normalized_cmp(_extract_alias_from_agent(candidate)) == target:
            return candidate
    return None


def _find_agent_by_voip(mapped_voip: str, db: Any):
    from app.models import DatoImportado, PagoSemanal

    target = _normalized_cmp(mapped_voip)
    if not target:
        return None

    candidates = (
        db.query(DatoImportado)
        .filter(DatoImportado.es_activo.is_(True))
        .all()
    )
    for candidate in candidates:
        if _normalized_cmp(_extract_voip_from_agent(candidate)) == target:
            return candidate

    pago = (
        db.query(PagoSemanal)
        .filter(PagoSemanal.numero_voip == mapped_voip)
        .order_by(PagoSemanal.id.desc())
        .first()
    )
    if pago:
        return db.query(DatoImportado).filter(DatoImportado.id == pago.agente_id).first()
    return None


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

    alias = str(mapped_row.get("alias") or "").strip()
    if alias:
        by_alias = _find_agent_by_alias_scan(alias, db)
        if by_alias:
            return by_alias

    nombre = str(mapped_row.get("nombre") or "").strip()
    if nombre:
        by_name = (
            db.query(DatoImportado)
            .filter(DatoImportado.nombre == nombre)
            .first()
        )
        if by_name:
            return by_name

    numero_voip = str(mapped_row.get("numero_voip") or "").strip()
    if numero_voip:
        by_voip = _find_agent_by_voip(numero_voip, db)
        if by_voip:
            return by_voip
    return None


def get_active_line_context(agent_id: int, db: Any) -> dict:
    from app.models import AgenteLineaAsignacion, LineaTelefonica

    assignment = (
        db.query(AgenteLineaAsignacion)
        .filter(
            AgenteLineaAsignacion.agente_id == agent_id,
            AgenteLineaAsignacion.es_activa.is_(True),
        )
        .order_by(AgenteLineaAsignacion.id.desc())
        .first()
    )
    if not assignment:
        return {
            "assignment": None,
            "line": None,
            "line_number": None,
        }

    line = (
        db.query(LineaTelefonica)
        .filter(LineaTelefonica.id == assignment.linea_id)
        .first()
    )
    return {
        "assignment": assignment,
        "line": line,
        "line_number": str(getattr(line, "numero", "") or "").strip() if line else None,
    }


def plan_line_update(agent_id: int, mapped_row: dict, db: Any) -> dict:
    from app.models import AgenteLineaAsignacion, LineaTelefonica

    target_number = str(mapped_row.get("numero_voip") or "").strip()
    if not target_number:
        return {"accion": "sin_dato_voip", "detalle": "Fila sin numero_voip mapeado."}

    current = get_active_line_context(agent_id, db)
    if _normalized_cmp(current.get("line_number")) == _normalized_cmp(target_number):
        return {"accion": "sin_cambio", "numero": target_number}

    target_line = db.query(LineaTelefonica).filter(LineaTelefonica.numero == target_number).first()
    if not target_line:
        return {
            "accion": "crear_y_asignar",
            "numero": target_number,
            "linea_id": None,
        }

    ocupacion = (
        db.query(AgenteLineaAsignacion)
        .filter(
            AgenteLineaAsignacion.linea_id == target_line.id,
            AgenteLineaAsignacion.es_activa.is_(True),
        )
        .order_by(AgenteLineaAsignacion.id.desc())
        .first()
    )

    if ocupacion and ocupacion.agente_id != agent_id:
        return {
            "accion": "conflicto_linea_ocupada",
            "numero": target_number,
            "linea_id": target_line.id,
            "agente_ocupante_id": ocupacion.agente_id,
        }

    return {
        "accion": "reasignar_existente",
        "numero": target_number,
        "linea_id": target_line.id,
    }


_TEST_DATA_PATTERNS = [
    re.compile(r"\b(test|qa|demo|prueba|dummy|sample|xxxx)\b", re.IGNORECASE),
    re.compile(r"@(example\.com|test\.com|mailinator\.com)$", re.IGNORECASE),
]


def _detect_test_data(mapped_row: dict) -> list[str]:
    findings: list[str] = []
    for field in ("nombre", "alias", "email"):
        value = str(mapped_row.get(field) or "").strip()
        if not value:
            continue
        if any(pattern.search(value) for pattern in _TEST_DATA_PATTERNS):
            findings.append(f"Posible dato de prueba en campo '{field}': {value}")
    return findings


def _detect_incoherencias(mapped_row: dict) -> list[str]:
    issues: list[str] = []

    phone = re.sub(r"\D", "", str(mapped_row.get("telefono") or ""))
    if phone and len(phone) < 8:
        issues.append("Telefono con longitud menor a 8 digitos.")
    if phone and len(set(phone)) == 1 and len(phone) >= 8:
        issues.append("Telefono con digito repetido (posible placeholder).")

    voip = str(mapped_row.get("numero_voip") or "").strip()
    if voip and not re.fullmatch(r"[A-Za-z0-9_\-/]{2,20}", voip):
        issues.append("numero_voip con formato irregular.")

    if not str(mapped_row.get("alias") or "").strip() and str(mapped_row.get("nombre") or "").strip():
        issues.append("Alias ausente; se recomienda usar nombre como alias operativo.")

    ubic = str(mapped_row.get("ubicacion") or "").strip()
    if ubic and not re.search(r"\d", ubic):
        issues.append("Ubicacion sin componente numerico; validar formato.")

    return issues


def _build_row_risk(
    fila: int,
    accion: str,
    plan_linea: dict | None,
    test_findings: list[str],
    incoherencias: list[str],
) -> dict | None:
    """Create a prioritized risk record for operator review."""
    line_action = (plan_linea or {}).get("accion")

    if line_action == "conflicto_linea_ocupada":
        return {
            "fila": fila,
            "nivel": "alto",
            "categoria": "conflicto_linea",
            "detalle": f"Linea {plan_linea.get('numero')} ocupada por agente {plan_linea.get('agente_ocupante_id')}",
        }

    if incoherencias:
        return {
            "fila": fila,
            "nivel": "medio",
            "categoria": "incoherencia_datos",
            "detalle": " | ".join(incoherencias[:3]),
        }

    if test_findings:
        return {
            "fila": fila,
            "nivel": "medio",
            "categoria": "dato_prueba",
            "detalle": " | ".join(test_findings[:2]),
        }

    if accion == "actualizar":
        return {
            "fila": fila,
            "nivel": "bajo",
            "categoria": "actualizacion",
            "detalle": "Fila propone actualizacion sin conflicto critico.",
        }

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

    diagnostico = {
        "alertas_test_data": [],
        "incoherencias": [],
        "riesgos_priorizados": [],
        "sugerencias": [
            "Revisar filas con conflictos de linea antes de ejecutar.",
            "Confirmar alias operativo cuando venga vacio en archivo.",
        ],
    }

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
        cambios_detectados: dict[str, dict] = {}
        plan_linea: dict | None = None

        test_findings = _detect_test_data(mapped)
        incoherencias = _detect_incoherencias(mapped)
        if test_findings:
            diagnostico["alertas_test_data"].append({"fila": idx + 2, "hallazgos": test_findings})
        if incoherencias:
            diagnostico["incoherencias"].append({"fila": idx + 2, "hallazgos": incoherencias})

        if db is not None:
            existing = find_existing_agent(mapped, db)
            if existing:
                agente_id = existing.id
                # Compare updatable fields to detect actual changes
                extras = _safe_json_dict(existing.datos_adicionales)
                for f, incoming in mapped.items():
                    if f in _UPDATABLE_FIELDS:
                        current_value = str(getattr(existing, f, "") or "")
                    else:
                        current_value = str(extras.get(f, "") or "")
                    if current_value != incoming:
                        cambios_detectados[f] = {
                            "actual": current_value,
                            "nuevo": incoming,
                        }

                if "alias" not in mapped and str(mapped.get("nombre") or "").strip():
                    current_alias = str(extras.get("alias") or "").strip()
                    if not current_alias:
                        cambios_detectados["alias"] = {
                            "actual": "",
                            "nuevo": str(mapped.get("nombre") or "").strip(),
                            "motivo": "fallback_nombre",
                        }

                plan_linea = plan_line_update(existing.id, mapped, db)
                if cambios_detectados:
                    accion = "actualizar"
                    actualizaciones += 1
                else:
                    accion = "sin_cambio"
                    sin_cambios += 1
                tiene_numero = agent_has_active_line(existing.id, db)

                if accion == "sin_cambio" and plan_linea and plan_linea.get("accion") not in {"sin_cambio", "sin_dato_voip"}:
                    accion = "actualizar"
                    actualizaciones += 1
                    sin_cambios = max(0, sin_cambios - 1)
            else:
                if db is not None:
                    plan_linea = plan_line_update(0, mapped, db)
                nuevos += 1
        else:
            nuevos += 1

        risk = _build_row_risk(
            fila=idx + 2,
            accion=accion,
            plan_linea=plan_linea,
            test_findings=test_findings,
            incoherencias=incoherencias,
        )
        if risk:
            diagnostico["riesgos_priorizados"].append(risk)

        filas_preview.append(
            {
                "fila": idx + 2,
                "accion": accion,
                "datos_mapeados": mapped,
                "agente_existente_id": agente_id,
                "tiene_numero": tiene_numero,
                "cambios_detectados": cambios_detectados,
                "plan_linea": plan_linea,
            }
        )

    priority = {"alto": 0, "medio": 1, "bajo": 2}
    diagnostico["riesgos_priorizados"].sort(key=lambda x: (priority.get(x.get("nivel"), 9), int(x.get("fila", 0))))

    return {
        "nuevos": nuevos,
        "actualizaciones": actualizaciones,
        "sin_cambios": sin_cambios,
        "filas_preview": filas_preview,
        "errores_formato": formato_errors,
        "diagnostico_ai": diagnostico,
    }


def apply_agent_row_changes(existing: Any, mapped: dict, db: Any) -> dict:
    """Apply mapped field changes to an existing agent and return mutation metadata."""
    direct_changed = 0
    extras_changed = 0
    extras = _safe_json_dict(existing.datos_adicionales)

    for field, value in mapped.items():
        if field in _UPDATABLE_FIELDS:
            current = str(getattr(existing, field, "") or "")
            if current != value:
                setattr(existing, field, value)
                direct_changed += 1
        else:
            current = str(extras.get(field, "") or "")
            if current != value:
                extras[field] = value
                extras_changed += 1

    if "alias" not in mapped:
        fallback_alias = str(mapped.get("nombre") or "").strip()
        if fallback_alias and not str(extras.get("alias") or "").strip():
            extras["alias"] = fallback_alias
            extras_changed += 1

    existing.datos_adicionales = json.dumps(extras, ensure_ascii=False) if extras else None
    db.add(existing)

    return {
        "direct_changed": direct_changed,
        "extras_changed": extras_changed,
    }


def apply_line_plan(agent_id: int, mapped: dict, db: Any) -> dict:
    from app.models import AgenteLineaAsignacion, LineaTelefonica

    plan = plan_line_update(agent_id, mapped, db)
    action = plan.get("accion")

    if action in {"sin_dato_voip", "sin_cambio", "conflicto_linea_ocupada"}:
        return plan

    target_number = str(plan.get("numero") or "").strip()
    line = None

    if action == "crear_y_asignar":
        line = LineaTelefonica(
            numero=target_number,
            tipo="VOIP",
            descripcion="Creada por smart-import",
            es_activa=True,
        )
        db.add(line)
        db.flush()
    elif action == "reasignar_existente":
        line = db.query(LineaTelefonica).filter(LineaTelefonica.id == plan.get("linea_id")).first()

    if not line:
        return {
            "accion": "error",
            "detalle": "No se pudo resolver linea objetivo.",
        }

    current_ctx = get_active_line_context(agent_id, db)
    current_assignment = current_ctx.get("assignment")
    if current_assignment and current_assignment.linea_id != line.id:
        current_assignment.es_activa = False
        current_assignment.fecha_liberacion = None
        db.add(current_assignment)

    already_assigned = (
        db.query(AgenteLineaAsignacion)
        .filter(
            AgenteLineaAsignacion.agente_id == agent_id,
            AgenteLineaAsignacion.linea_id == line.id,
            AgenteLineaAsignacion.es_activa.is_(True),
        )
        .first()
    )
    if not already_assigned:
        db.add(
            AgenteLineaAsignacion(
                agente_id=agent_id,
                linea_id=line.id,
                es_activa=True,
                observaciones="Asignada por smart-import",
            )
        )

    return {
        "accion": action,
        "linea_id": line.id,
        "numero": line.numero,
    }
