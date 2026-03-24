"""Endpoints de verificacion QR para agentes y pagos semanales."""

from datetime import UTC, date, datetime, timedelta
import json
import logging
import os
import re
import secrets
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.database.orm import get_db
from app.models import (
    AgenteLadaPreferencia,
    AgenteLineaAsignacion,
    AlertaPago,
    DatoImportado,
    LadaCatalogo,
    LineaTelefonica,
    PagoSemanal,
    ReciboPago,
)
from app.schemas import PagoSemanalCrear, PagoSemanalAdminActualizar
from app.security import get_current_user, require_admin_role, require_capture_role
from app.qr import QRGenerator
from app.config import config
from app.services.lineas import (
    build_empty_line_sync_result,
    extract_lada_from_number,
    normalize_categoria_linea,
    normalize_estado_conexion,
    normalize_lada,
    parse_fecha_ultimo_uso,
    serialize_linea_operativa,
)
from app.services.qr_security import decode_secure_qr_token
from app.utils.backups import (
    create_weekly_backup,
    get_backup_settings,
    list_backups,
    restore_backup,
    set_backup_dir,
)
from app.utils.qr_print import build_agent_qr_pdf
from app.utils.pagos import (
    generar_alertas_miercoles_pendientes,
    get_cuota_semanal,
    monday_of_week,
    obtener_reporte_semanal,
    resumen_cobranza_agente,
    set_manual_deuda_ajuste,
    set_cuota_semanal,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/qr", tags=["QR Verificacion"])
NO_PHONE_VALUE = "SIN_TELEFONO"

UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
SYNCED_EXTENSION_TYPE = "EXT_PBX"
SYNCED_EXTENSION_PREFIX = "SYNC extensions_pbx"
LEGACY_AGENTES_DB = "registro_agentes"
LEGACY_AGENTES_TABLE = "agentes"
LEGACY_LADAS_TABLE = "catalogo_ladas"


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _active_assignment_for_agent(db: Session, agente_id: int) -> AgenteLineaAsignacion | None:
    return db.query(AgenteLineaAsignacion).filter(
        AgenteLineaAsignacion.agente_id == agente_id,
        AgenteLineaAsignacion.es_activa.is_(True),
    ).order_by(AgenteLineaAsignacion.fecha_asignacion.desc()).first()


def _build_static_agent_public_url(agente: DatoImportado) -> str:
    public_base_url = config.get_public_base_url()
    return f"{public_base_url}/api/qr/public/verify/{agente.uuid}"


def _validate_secure_qr_token(db: Session, token: str, *, require_current: bool = True) -> tuple[DatoImportado, LineaTelefonica | None, dict]:
    payload = decode_secure_qr_token(token)
    agente_id = int(payload.get("agente_id") or 0)
    linea_id = int(payload.get("linea_id") or 0)

    agente = db.query(DatoImportado).filter(
        DatoImportado.id == agente_id,
        DatoImportado.es_activo.is_(True),
    ).first()
    if not agente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente no encontrado")

    linea = None
    if linea_id > 0:
        linea = db.query(LineaTelefonica).filter(
            LineaTelefonica.id == linea_id,
            LineaTelefonica.es_activa.is_(True),
        ).first()
    if linea_id > 0 and not linea:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Linea del QR ya no esta activa")

    active_assignment = _active_assignment_for_agent(db, agente.id)
    if require_current and (not active_assignment or active_assignment.linea_id != linea_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="QR invalido para la linea actualmente asignada")

    if require_current:
        stored_payload = _safe_json_object(agente.contenido_qr)
        current_token = str(stored_payload.get("secure_token") or "").strip()
        if current_token and current_token != str(token).strip():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="QR reemplazado por una version mas reciente")

    return agente, linea, payload


def _cleanup_expired_receipts(db: Session) -> None:
    db.query(ReciboPago).filter(ReciboPago.expira_en < _utcnow()).delete(synchronize_session=False)


def _build_receipt_payload(*, pago: PagoSemanal, agente: DatoImportado, linea: LineaTelefonica | None) -> dict:
    return {
        "pago_id": pago.id,
        "agente_id": agente.id,
        "agente_nombre": agente.nombre,
        "linea_id": linea.id if linea else None,
        "linea_numero": linea.numero if linea else None,
        "telefono": pago.telefono,
        "numero_voip": pago.numero_voip,
        "semana_inicio": pago.semana_inicio.isoformat() if pago.semana_inicio else None,
        "monto": float(pago.monto or 0),
        "pagado": bool(pago.pagado),
        "fecha_pago": pago.fecha_pago.isoformat() if pago.fecha_pago else None,
        "observaciones": pago.observaciones,
    }


def _upsert_payment_receipt(db: Session, *, pago: PagoSemanal, agente: DatoImportado, linea: LineaTelefonica | None) -> ReciboPago:
    _cleanup_expired_receipts(db)
    retention_days = max(1, int(config.RECEIPT_RETENTION_DAYS or 1))
    expires_at = _utcnow() + timedelta(days=retention_days)
    payload = _build_receipt_payload(pago=pago, agente=agente, linea=linea)
    existing = db.query(ReciboPago).filter(ReciboPago.pago_id == pago.id).first()
    if existing:
        existing.agente_id = agente.id
        existing.linea_id = linea.id if linea else None
        existing.linea_numero = linea.numero if linea else None
        existing.contenido_json = json.dumps(payload, ensure_ascii=False)
        existing.expira_en = expires_at
        return existing

    row = ReciboPago(
        pago_id=pago.id,
        agente_id=agente.id,
        linea_id=linea.id if linea else None,
        linea_numero=linea.numero if linea else None,
        token_recibo=secrets.token_urlsafe(24),
        contenido_json=json.dumps(payload, ensure_ascii=False),
        expira_en=expires_at,
    )
    db.add(row)
    return row


def _safe_sql_identifier(raw: str | None, fallback: str) -> str:
    value = str(raw or "").strip() or fallback
    if not re.match(r"^[0-9A-Za-z_]+$", value):
        return fallback
    return value


def _managed_extension_description() -> str:
    return (
        f"{SYNCED_EXTENSION_PREFIX} "
        f"{_safe_sql_identifier(config.PBX_DB_NAME, 'registro_agentes')}."
        f"{_safe_sql_identifier(config.PBX_EXTENSIONS_TABLE, 'extensions_pbx')}"
    )


def _managed_extension_filter():
    return LineaTelefonica.descripcion.ilike(f"{SYNCED_EXTENSION_PREFIX}%")


def _fetch_extension_source_numbers(db: Session) -> list[str]:
    source_db = _safe_sql_identifier(config.PBX_DB_NAME, "registro_agentes")
    source_table = _safe_sql_identifier(config.PBX_EXTENSIONS_TABLE, "extensions_pbx")
    rows = db.execute(
        text(
            f"SELECT CAST(`Extension` AS CHAR) AS extension "
            f"FROM `{source_db}`.`{source_table}`"
        )
    ).mappings().all()

    numbers: list[str] = []
    seen: set[str] = set()
    for row in rows:
        raw_value = row.get("extension")
        if raw_value in (None, ""):
            continue
        try:
            numero = _safe_line_number(str(raw_value))
        except HTTPException:
            continue
        if numero in seen:
            continue
        seen.add(numero)
        numbers.append(numero)
    return numbers


def _sync_extensions_inventory(db: Session) -> dict[str, int]:
    desired_description = _managed_extension_description()
    try:
        source_numbers = _fetch_extension_source_numbers(db)
    except Exception as exc:
        logger.warning("No se pudo sincronizar inventario extensions_pbx; se mantiene inventario local activo", exc_info=exc)
        source_numbers = []
    source_set = set(source_numbers)
    existing_lines = {row.numero: row for row in db.query(LineaTelefonica).all()}
    now = _utcnow()
    created = 0
    updated = 0
    deactivated = 0

    for numero in source_numbers:
        row = existing_lines.get(numero)
        if row is None:
            db.add(
                LineaTelefonica(
                    numero=numero,
                    tipo=SYNCED_EXTENSION_TYPE,
                    descripcion=desired_description,
                    categoria_linea="NO_DEFINIDA",
                    estado_conexion="DESCONOCIDA",
                    es_activa=True,
                )
            )
            created += 1
            continue

        changed = False
        if not row.es_activa:
            row.es_activa = True
            changed = True
        if row.tipo != SYNCED_EXTENSION_TYPE:
            row.tipo = SYNCED_EXTENSION_TYPE
            changed = True
        if row.descripcion != desired_description:
            row.descripcion = desired_description
            changed = True
        if not row.categoria_linea:
            row.categoria_linea = "NO_DEFINIDA"
            changed = True
        if not row.estado_conexion:
            row.estado_conexion = "DESCONOCIDA"
            changed = True
        if changed:
            row.fecha_actualizacion = now
            updated += 1

    managed_rows = db.query(LineaTelefonica).filter(_managed_extension_filter()).all()
    for row in managed_rows:
        if row.numero in source_set or not row.es_activa:
            continue
        row.es_activa = False
        row.fecha_actualizacion = now
        deactivated += 1
        active_assignments = db.query(AgenteLineaAsignacion).filter(
            AgenteLineaAsignacion.linea_id == row.id,
            AgenteLineaAsignacion.es_activa.is_(True),
        ).all()
        for assignment in active_assignments:
            assignment.es_activa = False
            assignment.fecha_liberacion = now
            assignment.observaciones = (
                assignment.observaciones or "Liberada por sincronizacion extensions_pbx"
            )

    ladas_created = 0
    ladas_reactivated = 0
    ladas_known = {row.codigo: row for row in db.query(LadaCatalogo).all()}
    source_ladas = sorted({numero[:3] for numero in source_numbers if len(numero) >= 3})
    for lada_code in source_ladas:
        existing_lada = ladas_known.get(lada_code)
        if existing_lada is None:
            db.add(LadaCatalogo(codigo=lada_code, nombre_region=None, es_activa=True))
            ladas_created += 1
            continue
        if not existing_lada.es_activa:
            existing_lada.es_activa = True
            ladas_reactivated += 1

    db.flush()
    return {
        "source": len(source_numbers),
        "created": created,
        "updated": updated,
        "deactivated": deactivated,
        "ladas_created": ladas_created,
        "ladas_reactivated": ladas_reactivated,
    }


def _sync_ladas_from_legacy_catalog(db: Session) -> dict[str, int]:
    """Importar/actualizar ladas desde registro_agentes.catalogo_ladas hacia ladas_catalogo."""
    source_db = _safe_sql_identifier(config.PBX_DB_NAME, "registro_agentes")
    source_table = _safe_sql_identifier(LEGACY_LADAS_TABLE, "catalogo_ladas")
    rows = db.execute(
        text(
            f"""
            SELECT
                CAST(`LADA` AS CHAR) AS codigo,
                CAST(`CIUDAD` AS CHAR) AS ciudad,
                CAST(`ESTADO` AS CHAR) AS estado,
                CAST(`PAIS` AS CHAR) AS pais
            FROM `{source_db}`.`{source_table}`
            WHERE `LADA` IS NOT NULL
            """
        )
    ).mappings().all()

    existing = {row.codigo: row for row in db.query(LadaCatalogo).all()}
    normalized_rows: dict[str, dict[str, str]] = {}

    for row in rows:
        raw_code = row.get("codigo")
        try:
            codigo = normalize_lada(str(raw_code or ""))
        except HTTPException:
            continue

        ciudad = str(row.get("ciudad") or "").strip()
        estado = str(row.get("estado") or "").strip()
        pais = str(row.get("pais") or "").strip()
        nombre_region = ", ".join([part for part in [ciudad, estado] if part]) or (pais or None)
        normalized_rows[codigo] = {
            "nombre_region": nombre_region,
        }

    created = 0
    updated = 0
    reactivated = 0

    for codigo, payload in normalized_rows.items():
        nombre_region = payload["nombre_region"]

        current = existing.get(codigo)
        if not current:
            db.add(LadaCatalogo(codigo=codigo, nombre_region=nombre_region, es_activa=True))
            existing[codigo] = True
            created += 1
            continue

        changed = False
        if not current.es_activa:
            current.es_activa = True
            reactivated += 1
            changed = True
        if nombre_region and current.nombre_region != nombre_region:
            current.nombre_region = nombre_region
            changed = True
        if changed:
            updated += 1

    db.flush()
    return {
        "source": len(rows),
        "normalized": len(normalized_rows),
        "created": created,
        "updated": updated,
        "reactivated": reactivated,
    }


def _get_managed_active_line_query(db: Session):
    return db.query(LineaTelefonica).filter(
        LineaTelefonica.es_activa.is_(True),
        _managed_extension_filter(),
    )


def _get_active_line_query(db: Session):
    return db.query(LineaTelefonica).filter(LineaTelefonica.es_activa.is_(True))


def _render_public_status_page(payload: dict) -> HTMLResponse:
    """Render a public verification page with current payment and debt status."""
    agente = payload.get("agente", {})
    pagado = bool(payload.get("pagado", False))
    asignado = bool(agente.get("tiene_asignacion", False))
    saldo_acumulado = float(payload.get("saldo_acumulado", 0.0) or 0.0)
    deuda_total = float(payload.get("deuda_total", 0.0) or 0.0)
    total_abonado = float(payload.get("total_abonado", 0.0) or 0.0)
    semanas_pendientes = int(payload.get("semanas_pendientes", 0) or 0)
    linea = str(agente.get("linea") or "-")
    pago_url = str(payload.get("pago_url") or "").strip()
    color = "#16966a" if pagado else "#d64545"
    label = "Al Corriente" if pagado else "Pendiente de Pago"
    asignacion = "NUMERO ASIGNADO" if asignado else "SIN NUMERO ASIGNADO"
    action_html = f"<a class=\"cta\" href=\"{pago_url}\">Registrar pago de este agente</a>" if pago_url else ""
    html = f"""
    <!doctype html>
    <html lang=\"es\">
    <head>
        <meta charset=\"utf-8\">
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
        <title>Verificación de Pago</title>
        <style>
            body {{ font-family: Segoe UI, Arial, sans-serif; margin: 0; background: #f4f7fb; color: #1a2330; }}
            .wrap {{ max-width: 820px; margin: 40px auto; padding: 20px; }}
            .card {{ background: #fff; border-radius: 18px; box-shadow: 0 12px 30px rgba(0,0,0,.10); overflow: hidden; }}
            .hero {{ background: {color}; color: #fff; padding: 28px; text-align: center; }}
            .hero h1 {{ margin: 0; font-size: 2rem; }}
            .badge {{ display: inline-block; margin-top: 12px; padding: 8px 18px; border-radius: 999px; background: rgba(255,255,255,.18); font-weight: 700; }}
            .body {{ padding: 24px; font-size: 1rem; line-height: 1.6; }}
            .row {{ margin-bottom: 10px; }}
            .label {{ font-weight: 700; }}
            .cta {{ display: inline-block; margin-top: 14px; padding: 10px 16px; border-radius: 10px; background: #0f6ecf; color: #fff; text-decoration: none; font-weight: 700; }}
            .cta:hover {{ filter: brightness(1.08); }}
        </style>
    </head>
    <body>
        <div class=\"wrap\">
            <div class=\"card\">
                <div class=\"hero\">
                    <h1>{agente.get('nombre', 'Agente')}</h1>
                    <div class=\"badge\">{label}</div>
                </div>
                <div class=\"body\">
                    <div class=\"row\"><span class=\"label\">ID:</span> {agente.get('id', agente.get('uuid', '-'))}</div>
                    <div class=\"row\"><span class=\"label\">Telefono:</span> {agente.get('telefono', '-')}</div>
                    <div class=\"row\"><span class=\"label\">Asignacion:</span> {asignacion}</div>
                    <div class=\"row\"><span class=\"label\">Linea activa:</span> {linea}</div>
                    <div class=\"row\"><span class=\"label\">Semana:</span> {payload.get('semana_inicio', '-')}</div>
                    <div class=\"row\"><span class=\"label\">Monto semana:</span> ${float(payload.get('monto', 0.0)):.2f} MXN</div>
                    <div class=\"row\"><span class=\"label\">Total abonado:</span> ${total_abonado:.2f} MXN</div>
                    <div class=\"row\"><span class=\"label\">Deuda total:</span> ${deuda_total:.2f} MXN</div>
                    <div class=\"row\"><span class=\"label\">Saldo acumulado:</span> ${saldo_acumulado:.2f} MXN</div>
                    <div class=\"row\"><span class=\"label\">Semanas pendientes:</span> {semanas_pendientes}</div>
                    <div class=\"row\"><span class=\"label\">Fecha de pago:</span> {payload.get('fecha_pago') or 'Sin registro'}</div>
                    {action_html}
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


def _extract_voip(dato: DatoImportado) -> str | None:
    """Try to extract voip number from datos_adicionales JSON."""
    if not dato.datos_adicionales:
        return None
    try:
        data = json.loads(dato.datos_adicionales)
    except Exception:
        return None

    for key in ("numero_voip", "voip", "extension", "ext"):
        if key in data and data[key] is not None:
            return str(data[key])
    return None


def _safe_json_object(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _legacy_text(raw: str | None, max_len: int) -> str:
    value = str(raw or "").strip()
    if len(value) > max_len:
        return value[:max_len]
    return value


def _nullable_payload_text(raw: object) -> str | None:
    value = str(raw or "").strip()
    if not value:
        return None
    if value.lower() == "null":
        return None
    return value


def _sync_legacy_agente_row(db: Session, *, agente_id: int, nombre: str, datos_adicionales: dict | None = None) -> None:
    extras = datos_adicionales if isinstance(datos_adicionales, dict) else {}
    db_name = _safe_sql_identifier(LEGACY_AGENTES_DB, "registro_agentes")
    table_name = _safe_sql_identifier(LEGACY_AGENTES_TABLE, "agentes")
    db.execute(
        text(
            f"""
            INSERT INTO `{db_name}`.`{table_name}`
                (`ID`, `Nombre`, `alias`, `Ubicacion`, `FP`, `FC`, `Grupo`)
            VALUES
                (:id, :nombre, :alias, :ubicacion, :fp, :fc, :grupo)
            ON DUPLICATE KEY UPDATE
                `Nombre` = VALUES(`Nombre`),
                `alias` = VALUES(`alias`),
                `Ubicacion` = VALUES(`Ubicacion`),
                `FP` = VALUES(`FP`),
                `FC` = VALUES(`FC`),
                `Grupo` = VALUES(`Grupo`)
            """
        ),
        {
            "id": int(agente_id),
            "nombre": _legacy_text(nombre, 50),
            "alias": _legacy_text(extras.get("alias"), 50),
            "ubicacion": _legacy_text(extras.get("ubicacion"), 10),
            "fp": _legacy_text(extras.get("fp"), 10),
            "fc": _legacy_text(extras.get("fc"), 10),
            "grupo": _legacy_text(extras.get("grupo"), 10),
        },
    )


def _legacy_agent_display_name(raw_name: str | None, raw_alias: str | None, agente_id: int) -> str:
    nombre = str(raw_name or "").strip()
    alias = str(raw_alias or "").strip()
    if nombre:
        return nombre
    if alias:
        return alias
    return f"Agente {int(agente_id)}"


def _sync_agents_from_legacy_table(db: Session, *, activate_existing: bool = True, limit: int = 2000) -> dict[str, int]:
    """Sincronizar agentes legacy (registro_agentes.agentes) hacia datos_importados sin asignar línea."""
    db_name = _safe_sql_identifier(LEGACY_AGENTES_DB, "registro_agentes")
    table_name = _safe_sql_identifier(LEGACY_AGENTES_TABLE, "agentes")
    max_rows = max(1, min(int(limit or 2000), 20000))

    rows = db.execute(
        text(
            f"""
            SELECT
                `ID` AS agente_id,
                `Nombre` AS nombre,
                `alias` AS alias,
                `Ubicacion` AS ubicacion,
                `FP` AS fp,
                `FC` AS fc,
                `Grupo` AS grupo
            FROM `{db_name}`.`{table_name}`
            WHERE `ID` IS NOT NULL
            ORDER BY `ID` ASC
            LIMIT :max_rows
            """
        ),
        {"max_rows": max_rows},
    ).mappings().all()

    created = 0
    updated = 0
    reactivated = 0
    skipped = 0

    for row in rows:
        agente_id = int(row.get("agente_id") or 0)
        if agente_id <= 0:
            skipped += 1
            continue

        extras = {
            "alias": _legacy_text(row.get("alias"), 50) or None,
            "ubicacion": _legacy_text(row.get("ubicacion"), 20) or None,
            "fp": _legacy_text(row.get("fp"), 20) or None,
            "fc": _legacy_text(row.get("fc"), 20) or None,
            "grupo": _legacy_text(row.get("grupo"), 20) or None,
        }
        extras = {k: v for k, v in extras.items() if v not in (None, "")}

        nombre_final = _legacy_agent_display_name(row.get("nombre"), row.get("alias"), agente_id)
        existing = db.query(DatoImportado).filter(DatoImportado.id == agente_id).first()

        if not existing:
            nuevo = DatoImportado(
                id=agente_id,
                nombre=nombre_final,
                telefono=None,
                email=None,
                empresa=None,
                ciudad=None,
                pais=None,
                datos_adicionales=json.dumps(extras, ensure_ascii=False) if extras else None,
                estatus_codigo="ACTIVO",
                es_activo=True,
            )
            db.add(nuevo)
            created += 1
            continue

        changed = False
        if activate_existing and not bool(existing.es_activo):
            existing.es_activo = True
            reactivated += 1
            changed = True

        if not str(existing.nombre or "").strip():
            existing.nombre = nombre_final
            changed = True

        current_extras = _safe_json_object(existing.datos_adicionales)
        merged = dict(current_extras)
        for key, value in extras.items():
            if key not in merged or not str(merged.get(key) or "").strip():
                merged[key] = value
                changed = True
        if changed:
            existing.datos_adicionales = json.dumps(merged, ensure_ascii=False) if merged else None
            updated += 1

    db.flush()
    return {
        "legacy_rows": len(rows),
        "created": created,
        "updated": updated,
        "reactivated": reactivated,
        "skipped": skipped,
        "limit": max_rows,
    }


def _refresh_agent_qr_for_state(db: Session, agente: DatoImportado, request: Request | None = None) -> dict:
    """Generar QR estatico por agente y guardar snapshot operativo actual."""
    active_assignment = _active_assignment_for_agent(db, agente.id)
    linea = active_assignment.linea if active_assignment and active_assignment.linea and active_assignment.linea.es_activa else None
    public_url = _build_static_agent_public_url(agente)

    lineas_agente = _agent_active_lines(db, agente.id)
    payload = {
        "agente_id": agente.id,
        "uuid": agente.uuid,
        "nombre": agente.nombre,
        "telefono": agente.telefono,
        "numero_voip": _extract_voip(agente),
        "tiene_asignacion": bool(lineas_agente),
        "lineas": lineas_agente,
        "linea_activa": {
            "linea_id": linea.id if linea else None,
            "numero": linea.numero if linea else None,
            "tipo": linea.tipo if linea else None,
        } if linea else None,
        "linea_estado": "asignada" if linea else "sin_linea",
        "qr_mode": "static_uuid",
        "es_qr_estatico": True,
        "es_qr_seguro": False,
        "secure_token": None,
        "public_url": public_url,
    }

    generator = QRGenerator()
    filename = f"agente_{agente.id}_{agente.uuid}.png"
    filepath = generator.generate_qr_from_text(public_url, filename)

    agente.qr_filename = filename
    agente.contenido_qr = json.dumps(payload, ensure_ascii=False)
    db.add(agente)
    db.flush()

    return {**payload, "qr_filename": filename, "qr_path": filepath}


def _has_assignment(dato: DatoImportado) -> bool:
    return False


def _active_line_assignments_map(db: Session) -> dict[int, AgenteLineaAsignacion]:
    """Map linea_id -> active assignment for fast occupancy checks."""
    rows = db.query(AgenteLineaAsignacion).filter(AgenteLineaAsignacion.es_activa.is_(True)).all()
    return {row.linea_id: row for row in rows}


def _agent_active_lines(db: Session, agente_id: int) -> list[dict]:
    """Return active lines assigned to an agent."""
    rows = db.query(AgenteLineaAsignacion).filter(
        AgenteLineaAsignacion.agente_id == agente_id,
        AgenteLineaAsignacion.es_activa.is_(True),
    ).all()

    result = []
    for row in rows:
        if not row.linea or not row.linea.es_activa:
            continue
        result.append({
            "linea_id": row.linea.id,
            "numero": row.linea.numero,
            "tipo": row.linea.tipo,
            "fecha_asignacion": row.fecha_asignacion.isoformat() if row.fecha_asignacion else None,
        })
    return result


def _extract_identifier_from_code(raw_code: str) -> tuple[str, str]:
    """Resolve scanned content into an identifier type and value."""
    code = (raw_code or "").strip()
    if not code:
        return "", ""

    # URL payloads from generated QR.
    if code.lower().startswith(("http://", "https://")):
        try:
            parsed = urlparse(code)
            path = (parsed.path or "").rstrip("/")
            secure_match = re.search(r"/api/qr/public/verify-secure/([^/]+)$", path)
            if secure_match:
                return "secure_token", secure_match.group(1)
            uuid_match = re.search(r"/api/qr/public/verify/([^/]+)$", path)
            if uuid_match:
                return "uuid", uuid_match.group(1)

            id_match = re.search(r"/api/qr/public/verify-by-id/(\d+)$", path)
            if id_match:
                return "id", id_match.group(1)
        except Exception:
            pass

    # Raw UUID.
    if UUID_RE.match(code):
        return "uuid", code

    # Numeric payload from barcode readers.
    if code.isdigit():
        return "numeric", code

    return "raw", code


def _find_agent_by_scanned_code(db: Session, code: str) -> DatoImportado | None:
    """Locate an active agent from scanned QR/barcode content."""
    kind, value = _extract_identifier_from_code(code)
    if not value:
        return None

    if kind == "secure_token":
        try:
            agente, _linea, _payload = _validate_secure_qr_token(db, value, require_current=True)
            return agente
        except HTTPException:
            return None

    if kind == "uuid":
        return db.query(DatoImportado).filter(
            DatoImportado.uuid == value,
            DatoImportado.es_activo.is_(True),
        ).first()

    if kind == "id":
        return db.query(DatoImportado).filter(
            DatoImportado.id == int(value),
            DatoImportado.es_activo.is_(True),
        ).first()

    if kind == "numeric":
        by_id = db.query(DatoImportado).filter(
            DatoImportado.id == int(value),
            DatoImportado.es_activo.is_(True),
        ).first()
        if by_id:
            return by_id

        by_phone = db.query(DatoImportado).filter(
            DatoImportado.telefono == value,
            DatoImportado.es_activo.is_(True),
        ).first()
        if by_phone:
            return by_phone

        agents = db.query(DatoImportado).filter(DatoImportado.es_activo.is_(True)).all()
        for agent in agents:
            voip = (_extract_voip(agent) or "").strip()
            if voip and voip == value:
                return agent

        line = db.query(LineaTelefonica).filter(
            LineaTelefonica.numero == value,
            LineaTelefonica.es_activa.is_(True),
        ).first()
        if line:
            assignment = db.query(AgenteLineaAsignacion).filter(
                AgenteLineaAsignacion.linea_id == line.id,
                AgenteLineaAsignacion.es_activa.is_(True),
            ).first()
            if assignment and assignment.agente and assignment.agente.es_activo:
                return assignment.agente
        return None

    if kind == "raw":
        by_phone = db.query(DatoImportado).filter(
            DatoImportado.telefono == value,
            DatoImportado.es_activo.is_(True),
        ).first()
        if by_phone:
            return by_phone

    return None


def _safe_line_number(raw: str) -> str:
    value = str(raw or "").strip()
    if not value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Numero de linea requerido")
    if len(value) > 50:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Numero de linea demasiado largo")
    if not re.match(r"^[0-9A-Za-z_\-\+]+$", value):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Numero de linea invalido")
    return value


def _parse_week_start(raw_value: str | None) -> date | None:
    value = str(raw_value or "").strip()
    if not value:
        return None
    try:
        return monday_of_week(date.fromisoformat(value))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Semana de cobro inicial inválida") from exc


def _parse_initial_charge(raw_value) -> float:
    if raw_value in (None, ""):
        return 0.0
    try:
        amount = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cargo inicial inválido") from exc
    if amount < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cargo inicial no puede ser negativo")
    return amount


def _resolve_or_create_line_for_manual_assignment(db: Session, payload: dict) -> LineaTelefonica:
    _sync_extensions_inventory(db)
    payload_obj = payload or {}
    categoria_en_payload = "categoria_linea" in payload_obj
    estado_en_payload = "estado_conexion" in payload_obj
    categoria_linea = normalize_categoria_linea(payload_obj.get("categoria_linea"), default="NO_DEFINIDA")
    estado_conexion = normalize_estado_conexion(payload_obj.get("estado_conexion"), default="DESCONOCIDA")
    linea_id = int((payload or {}).get("linea_id") or 0)
    if linea_id > 0:
        linea = _get_active_line_query(db).filter(
            LineaTelefonica.id == linea_id,
        ).first()
        if not linea:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linea no encontrada")
        if categoria_en_payload:
            linea.categoria_linea = categoria_linea
        if estado_en_payload:
            linea.estado_conexion = estado_conexion
        if categoria_en_payload or estado_en_payload:
            linea.fecha_actualizacion = _utcnow()
        return linea

    raw_number = (payload or {}).get("numero_linea_manual")
    numero = _safe_line_number(raw_number)
    existing = _get_active_line_query(db).filter(LineaTelefonica.numero == numero).first()
    if not existing:
        existing_any = db.query(LineaTelefonica).filter(LineaTelefonica.numero == numero).first()
        if existing_any:
            existing_any.es_activa = True
            if categoria_en_payload:
                existing_any.categoria_linea = categoria_linea
            if estado_en_payload:
                existing_any.estado_conexion = estado_conexion
            if categoria_en_payload or estado_en_payload:
                existing_any.fecha_actualizacion = _utcnow()
            db.flush()
            return existing_any
        row = LineaTelefonica(
            numero=numero,
            tipo="MANUAL",
            descripcion="Alta manual desde flujo de agente",
            categoria_linea=categoria_linea,
            estado_conexion=estado_conexion,
            es_activa=True,
        )
        db.add(row)
        db.flush()
        return row
    if categoria_en_payload:
        existing.categoria_linea = categoria_linea
    if estado_en_payload:
        existing.estado_conexion = estado_conexion
    if categoria_en_payload or estado_en_payload:
        existing.fecha_actualizacion = _utcnow()
    return existing


def _choose_free_line_automatically(db: Session, lada_objetivo: str | None = None) -> LineaTelefonica | None:
    _sync_extensions_inventory(db)
    active_assignments = _active_line_assignments_map(db)
    lineas = _get_active_line_query(db).order_by(LineaTelefonica.numero.asc()).all()
    available = [l for l in lineas if l.id not in active_assignments]
    if not available:
        return None

    if lada_objetivo:
        filtered = [l for l in available if re.sub(r"\D", "", l.numero).startswith(lada_objetivo)]
        if filtered:
            return filtered[0]

    return available[0]


def _set_agent_lada_preference(db: Session, agente_id: int, lada_code: str | None) -> None:
    if not lada_code:
        return
    lada_code = normalize_lada(lada_code)
    lada = db.query(LadaCatalogo).filter(LadaCatalogo.codigo == lada_code).first()
    if not lada:
        lada = LadaCatalogo(codigo=lada_code, nombre_region=None, es_activa=True)
        db.add(lada)
        db.flush()

    existing = db.query(AgenteLadaPreferencia).filter(
        AgenteLadaPreferencia.agente_id == agente_id,
        AgenteLadaPreferencia.lada_id == lada.id,
    ).first()
    if existing:
        return

    db.add(AgenteLadaPreferencia(agente_id=agente_id, lada_id=lada.id, prioridad=1))


@router.post("/pagos")
async def registrar_pago_semanal(
    pago_in: PagoSemanalCrear,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Registrar pago semanal con soporte de abonos y liquidacion total."""
    agente = db.query(DatoImportado).filter(
        DatoImportado.id == pago_in.agente_id,
        DatoImportado.es_activo.is_(True)
    ).first()
    if not agente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente no encontrado")

    active_assignment = _active_assignment_for_agent(db, agente.id)
    linea_activa = active_assignment.linea if active_assignment and active_assignment.linea and active_assignment.linea.es_activa else None
    if not linea_activa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede registrar cobro sin línea activa asignada al agente",
        )

    semana = monday_of_week(pago_in.semana_inicio)
    resumen_prev = resumen_cobranza_agente(db, agente, semana)
    cuota = float(resumen_prev["cuota_semanal"])
    saldo_acumulado_prev = float(resumen_prev["saldo_acumulado"])

    monto_final = float(pago_in.monto or 0)
    if bool(pago_in.liquidar_total):
        monto_final = saldo_acumulado_prev
    elif monto_final <= 0 and pago_in.pagado:
        monto_final = cuota

    if monto_final <= 0 and saldo_acumulado_prev > 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debes indicar un abono mayor a 0 o marcar liquidar_total")

    telefono_final = str((pago_in.telefono or agente.telefono or NO_PHONE_VALUE)).strip()[:20] or NO_PHONE_VALUE
    voip_final = str((pago_in.numero_voip or _extract_voip(agente) or "")).strip() or None

    pago = db.query(PagoSemanal).filter(
        PagoSemanal.agente_id == pago_in.agente_id,
        PagoSemanal.semana_inicio == semana
    ).first()

    if not pago:
        pago = PagoSemanal(
            agente_id=pago_in.agente_id,
            telefono=telefono_final,
            numero_voip=voip_final,
            semana_inicio=semana,
            monto=monto_final,
            pagado=monto_final >= cuota,
            fecha_pago=_utcnow() if monto_final > 0 else None,
            observaciones=pago_in.observaciones,
        )
        db.add(pago)
    else:
        pago.telefono = telefono_final
        pago.numero_voip = voip_final
        pago.monto = float(pago.monto or 0) + float(monto_final)
        pago.pagado = bool(pago.monto >= cuota)
        pago.observaciones = pago_in.observaciones or pago.observaciones
        pago.fecha_pago = _utcnow() if monto_final > 0 else pago.fecha_pago

    if pago.pagado:
        alertas = db.query(AlertaPago).filter(
            AlertaPago.agente_id == pago_in.agente_id,
            AlertaPago.semana_inicio == semana,
            AlertaPago.atendida.is_(False)
        ).all()
        for alerta in alertas:
            alerta.atendida = True
            alerta.fecha_atendida = _utcnow()

    db.commit()
    db.refresh(pago)

    resumen_after = resumen_cobranza_agente(db, agente, semana)

    active_assignment = _active_assignment_for_agent(db, agente.id)
    linea = active_assignment.linea if active_assignment and active_assignment.linea else None
    recibo = _upsert_payment_receipt(db, pago=pago, agente=agente, linea=linea)
    db.commit()
    db.refresh(recibo)

    logger.info("Usuario %s registró pago semanal para agente %s", current_user.get("username"), pago_in.agente_id)
    return {
        "id": pago.id,
        "agente_id": pago.agente_id,
        "telefono": pago.telefono,
        "numero_voip": pago.numero_voip,
        "semana_inicio": pago.semana_inicio.isoformat() if pago.semana_inicio else None,
        "abono_registrado": float(monto_final),
        "monto": float(pago.monto or 0),
        "pagado": bool(pago.pagado),
        "fecha_pago": pago.fecha_pago.isoformat() if pago.fecha_pago else None,
        "observaciones": pago.observaciones,
        "saldo_acumulado": float(resumen_after["saldo_acumulado"]),
        "deuda_total": float(resumen_after["deuda_total"]),
        "total_abonado": float(resumen_after["total_abonado"]),
        "semanas_pendientes": int(resumen_after["semanas_pendientes"]),
        "recibo": {
            "token": recibo.token_recibo,
            "expira_en": recibo.expira_en.isoformat() if recibo.expira_en else None,
            "linea_numero": recibo.linea_numero,
        },
    }


@router.put("/pagos/{pago_id}")
async def editar_pago_semanal_admin(
    pago_id: int,
    payload: PagoSemanalAdminActualizar,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Permitir a administradores editar manualmente un pago semanal."""
    require_admin_role(current_user, "Solo admin puede editar manualmente pagos")
    pago = db.query(PagoSemanal).filter(PagoSemanal.id == pago_id).first()
    if not pago:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pago no encontrado")

    cuota = get_cuota_semanal(db)
    if payload.monto is not None:
        pago.monto = float(payload.monto)
    if payload.pagado is not None:
        pago.pagado = bool(payload.pagado)
    else:
        pago.pagado = bool((pago.monto or 0) >= cuota)
    if payload.observaciones is not None:
        pago.observaciones = payload.observaciones
    pago.fecha_pago = _utcnow() if pago.pagado else None

    db.add(pago)
    db.commit()
    db.refresh(pago)

    agente = db.query(DatoImportado).filter(DatoImportado.id == pago.agente_id).first()
    resumen = resumen_cobranza_agente(db, agente, pago.semana_inicio) if agente else None
    return {
        "status": "success",
        "data": {
            "id": pago.id,
            "agente_id": pago.agente_id,
            "semana_inicio": pago.semana_inicio.isoformat() if pago.semana_inicio else None,
            "monto": float(pago.monto or 0),
            "pagado": bool(pago.pagado),
            "fecha_pago": pago.fecha_pago.isoformat() if pago.fecha_pago else None,
            "observaciones": pago.observaciones,
            "saldo_acumulado": float((resumen or {}).get("saldo_acumulado", 0)),
        },
    }


@router.get("/pagos/resumen/{agente_id}")
async def resumen_pagos_agente(
    agente_id: int,
    semana: date | None = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Obtener resumen acumulado por agente para cobro y liquidaciones."""
    agente = db.query(DatoImportado).filter(
        DatoImportado.id == agente_id,
        DatoImportado.es_activo.is_(True),
    ).first()
    if not agente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente no encontrado")
    resumen = resumen_cobranza_agente(db, agente, semana)
    return {
        "status": "success",
        "agente": {"id": agente.id, "nombre": agente.nombre, "uuid": agente.uuid},
        "data": {
            **resumen,
            "semana_inicio": resumen["semana_inicio"].isoformat() if resumen.get("semana_inicio") else None,
        },
    }


@router.get("/agentes/{agente_id}/deuda-manual")
async def obtener_deuda_manual_agente(
    agente_id: int,
    semana: date | None = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Consultar ajuste manual de deuda y resumen actual del agente."""
    agente = db.query(DatoImportado).filter(
        DatoImportado.id == agente_id,
        DatoImportado.es_activo.is_(True),
    ).first()
    if not agente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente no encontrado")

    resumen = resumen_cobranza_agente(db, agente, semana)
    return {
        "status": "success",
        "agente": {"id": agente.id, "nombre": agente.nombre, "uuid": agente.uuid},
        "data": {
            "semana_inicio": resumen["semana_inicio"].isoformat() if resumen.get("semana_inicio") else None,
            "deuda_base_total": float(resumen.get("deuda_base_total") or 0),
            "ajuste_manual_deuda": float(resumen.get("ajuste_manual_deuda") or 0),
            "deuda_total": float(resumen.get("deuda_total") or 0),
            "total_abonado": float(resumen.get("total_abonado") or 0),
            "saldo_acumulado": float(resumen.get("saldo_acumulado") or 0),
            "lineas_activas": int(resumen.get("lineas_activas") or 0),
        },
    }


@router.put("/agentes/{agente_id}/deuda-manual")
async def actualizar_deuda_manual_agente(
    agente_id: int,
    payload: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Actualizar ajuste manual de deuda de un agente.

    modos:
    - ajuste: guarda monto directamente como ajuste (+/-) sobre deuda base.
    - saldo_objetivo: calcula ajuste para llegar al saldo acumulado deseado.
    """
    require_admin_role(current_user, "Solo admin puede editar deuda manual")
    agente = db.query(DatoImportado).filter(
        DatoImportado.id == agente_id,
        DatoImportado.es_activo.is_(True),
    ).first()
    if not agente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente no encontrado")

    mode = str((payload or {}).get("modo") or "ajuste").strip().lower()
    raw_monto = (payload or {}).get("monto")
    semana_raw = str((payload or {}).get("semana") or "").strip()
    semana_ref = None
    if semana_raw:
        try:
            semana_ref = date.fromisoformat(semana_raw)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Semana inválida") from exc

    if raw_monto in (None, ""):
        monto = 0.0
    else:
        try:
            monto = float(raw_monto)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Monto inválido") from exc

    if mode not in {"ajuste", "saldo_objetivo"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="modo debe ser ajuste o saldo_objetivo")

    if mode == "ajuste":
        nuevo_ajuste = set_manual_deuda_ajuste(db, agente.id, monto)
    else:
        resumen_prev = resumen_cobranza_agente(db, agente, semana_ref)
        deuda_base = float(resumen_prev.get("deuda_base_total") or 0)
        abonado = float(resumen_prev.get("total_abonado") or 0)
        target_deuda_total = max(float(monto) + abonado, 0.0)
        nuevo_ajuste = set_manual_deuda_ajuste(db, agente.id, target_deuda_total - deuda_base)

    resumen = resumen_cobranza_agente(db, agente, semana_ref)
    return {
        "status": "success",
        "agente": {"id": agente.id, "nombre": agente.nombre},
        "data": {
            "modo_aplicado": mode,
            "semana_inicio": resumen["semana_inicio"].isoformat() if resumen.get("semana_inicio") else None,
            "deuda_base_total": float(resumen.get("deuda_base_total") or 0),
            "ajuste_manual_deuda": float(resumen.get("ajuste_manual_deuda") or 0),
            "deuda_total": float(resumen.get("deuda_total") or 0),
            "total_abonado": float(resumen.get("total_abonado") or 0),
            "saldo_acumulado": float(resumen.get("saldo_acumulado") or 0),
            "lineas_activas": int(resumen.get("lineas_activas") or 0),
        },
    }


@router.get("/verificar/{agente_id}")
async def verificar_agente(
    agente_id: int,
    telefono: str | None = Query(None),
    numero_voip: str | None = Query(None),
    semana: date | None = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verificar agente, asignacion y estado de pago semanal."""
    agente = db.query(DatoImportado).filter(
        DatoImportado.id == agente_id,
        DatoImportado.es_activo.is_(True)
    ).first()
    if not agente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente no encontrado")

    voip_registrado = _extract_voip(agente)
    telefono_registrado = (agente.telefono or "").strip()

    telefono_valido = True if telefono is None else (telefono_registrado == telefono.strip())
    voip_valido = True if numero_voip is None else ((voip_registrado or "").strip() == numero_voip.strip())

    semana_ref = monday_of_week(semana or date.today())
    pago = db.query(PagoSemanal).filter(
        PagoSemanal.agente_id == agente_id,
        PagoSemanal.semana_inicio == semana_ref
    ).first()
    resumen_pago = resumen_cobranza_agente(db, agente, semana_ref)
    lineas_agente = _agent_active_lines(db, agente.id)
    tiene_asignacion = bool(lineas_agente)

    return {
        "status": "success",
        "agente": {
            "id": agente.id,
            "uuid": agente.uuid,
            "nombre": agente.nombre,
            "telefono": telefono_registrado,
            "numero_voip": voip_registrado,
            "empresa": agente.empresa,
            "es_activo": agente.es_activo,
            "tiene_asignacion": tiene_asignacion,
            "lineas": lineas_agente,
        },
        "verificacion": {
            "telefono_valido": telefono_valido,
            "voip_valido": voip_valido,
            "asignacion_valida": telefono_valido and voip_valido,
            "numero_asignado": tiene_asignacion,
            "semana_inicio": semana_ref.isoformat(),
            "pagado": bool(pago.pagado) if pago else False,
            "monto": float(pago.monto) if pago else 0.0,
            "tarifa_linea_semanal": float(resumen_pago["tarifa_linea_semanal"]),
            "lineas_activas": int(resumen_pago["lineas_activas"]),
            "cuota_semanal": float(resumen_pago["cuota_semanal"]),
            "deuda_base_total": float(resumen_pago.get("deuda_base_total") or 0),
            "ajuste_manual_deuda": float(resumen_pago.get("ajuste_manual_deuda") or 0),
            "deuda_total": float(resumen_pago["deuda_total"]),
            "total_abonado": float(resumen_pago["total_abonado"]),
            "saldo_acumulado": float(resumen_pago["saldo_acumulado"]),
            "semanas_pendientes": int(resumen_pago["semanas_pendientes"]),
            "fecha_pago": pago.fecha_pago.isoformat() if pago and pago.fecha_pago else None,
            "observaciones": pago.observaciones if pago else None,
        }
    }


@router.get("/verificar-uuid/{uuid}")
async def verificar_agente_por_uuid(
    uuid: str,
    semana: date | None = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verificar agente por UUID para escaneo interno de QR."""
    agente = db.query(DatoImportado).filter(
        DatoImportado.uuid == uuid,
        DatoImportado.es_activo.is_(True)
    ).first()
    if not agente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente no encontrado")
    return await verificar_agente(
        agente_id=agente.id,
        telefono=None,
        numero_voip=None,
        semana=semana,
        current_user=current_user,
        db=db,
    )


@router.post("/scan/verify")
async def verificar_por_codigo_escaneado(
    payload: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verificar agente leyendo codigo QR o codigo de barras."""
    code = str((payload or {}).get("code", "")).strip()
    if not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debe enviar code")

    semana_raw = (payload or {}).get("semana")
    semana = None
    if semana_raw:
        try:
            semana = date.fromisoformat(str(semana_raw))
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Semana invalida") from exc

    agente = _find_agent_by_scanned_code(db, code)
    if not agente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No se encontro agente para el codigo escaneado")

    return await verificar_agente(
        agente_id=agente.id,
        telefono=None,
        numero_voip=None,
        semana=semana,
        current_user=current_user,
        db=db,
    )


@router.get("/agentes")
async def listar_agentes_qr(
    search: str | None = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Listar agentes activos para asignacion de lineas y verificaciones."""
    query = db.query(DatoImportado).filter(DatoImportado.es_activo.is_(True))
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            (DatoImportado.nombre.ilike(term)) |
            (DatoImportado.telefono.ilike(term)) |
            (DatoImportado.empresa.ilike(term)) |
            (DatoImportado.datos_adicionales.ilike(term))
        )

    agentes = query.limit(500).all()
    agentes = sorted(
        agentes,
        key=lambda item: (
            str((_safe_json_object(item.datos_adicionales).get("alias") or "")).strip().lower() or "~",
            str(item.nombre or "").strip().lower() or "~",
            int(item.id or 0),
        ),
    )
    return {
        "status": "success",
        "data": [
            {
                "id": a.id,
                "uuid": a.uuid,
                "nombre": a.nombre,
                "alias": _safe_json_object(a.datos_adicionales).get("alias"),
                "display_name": _legacy_agent_display_name(a.nombre, _safe_json_object(a.datos_adicionales).get("alias"), a.id),
                "telefono": a.telefono,
                "numero_voip": _extract_voip(a),
                "datos_adicionales": _safe_json_object(a.datos_adicionales),
                "ladas_preferidas": [
                    pref.lada.codigo for pref in sorted(a.ladas_preferidas, key=lambda x: x.prioridad) if pref.lada and pref.lada.es_activa
                ],
                "lineas": _agent_active_lines(db, a.id),
            }
            for a in agentes
        ],
    }


@router.post("/agentes/sync-legacy")
async def sincronizar_agentes_legacy(
    payload: dict | None = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sincronizar agentes de registro_agentes.agentes hacia datos_importados sin asignar línea."""
    require_capture_role(current_user)
    activate_existing = bool((payload or {}).get("activate_existing", True))
    limit = int((payload or {}).get("limit", 2000) or 2000)

    result = _sync_agents_from_legacy_table(
        db,
        activate_existing=activate_existing,
        limit=limit,
    )
    db.commit()
    return {
        "status": "success",
        "message": "Sincronizacion legacy completada",
        "data": result,
    }


@router.post("/agentes/manual")
async def crear_agente_manual(
    payload: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Crear agente manualmente y asignar linea de forma opcional."""
    require_capture_role(current_user)
    nombre = _nullable_payload_text((payload or {}).get("nombre"))
    alias = _nullable_payload_text((payload or {}).get("alias"))
    if not nombre and not alias:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debe capturar al menos nombre o alias")

    email = _nullable_payload_text((payload or {}).get("email"))
    empresa = _nullable_payload_text((payload or {}).get("empresa"))
    ciudad = _nullable_payload_text((payload or {}).get("ciudad"))
    pais = _nullable_payload_text((payload or {}).get("pais"))

    datos_adicionales = {
        "alias": alias,
        "ubicacion": _nullable_payload_text((payload or {}).get("ubicacion")),
        "fp": _nullable_payload_text((payload or {}).get("fp")),
        "fc": _nullable_payload_text((payload or {}).get("fc")),
        "grupo": _nullable_payload_text((payload or {}).get("grupo")),
        "numero_voip": _nullable_payload_text((payload or {}).get("numero_voip")),
    }
    datos_adicionales = {k: v for k, v in datos_adicionales.items() if v not in (None, "")}

    modo = str((payload or {}).get("modo_asignacion") or "ninguna").strip().lower()
    if modo not in {"ninguna", "manual", "auto"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="modo_asignacion invalido")

    lada_objetivo = str((payload or {}).get("lada_objetivo") or "").strip() or None
    if lada_objetivo:
        lada_objetivo = normalize_lada(lada_objetivo)

    cobro_desde_semana = _parse_week_start((payload or {}).get("cobro_desde_semana"))
    cargo_inicial = _parse_initial_charge((payload or {}).get("cargo_inicial"))

    agente = DatoImportado(
        nombre=nombre,
        email=email,
        telefono=None,
        empresa=empresa,
        ciudad=ciudad,
        pais=pais,
        datos_adicionales=json.dumps(datos_adicionales, ensure_ascii=False) if datos_adicionales else None,
        estatus_codigo="ACTIVO",
        creado_por=current_user.get("id"),
        es_activo=True,
    )
    db.add(agente)
    db.flush()

    try:
        _sync_legacy_agente_row(
            db,
            agente_id=agente.id,
            nombre=agente.nombre or "",
            datos_adicionales=datos_adicionales,
        )
    except Exception as exc:
        dialect_name = str(getattr(getattr(db, "bind", None), "dialect", None).name if getattr(getattr(db, "bind", None), "dialect", None) else "")
        if dialect_name == "sqlite":
            # En pruebas locales con SQLite no existe ON DUPLICATE KEY de MariaDB.
            logger.warning("Sync legacy omitido en SQLite para alta manual de agente")
        else:
            logger.exception("No se pudo sincronizar alta manual en registro_agentes.agentes")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No fue posible guardar el agente en registro_agentes.agentes",
            ) from exc

    asignacion_resumen = {"modo": modo, "asignada": False}

    if modo == "manual":
        linea = _resolve_or_create_line_for_manual_assignment(db, payload)
        current = db.query(AgenteLineaAsignacion).filter(
            AgenteLineaAsignacion.linea_id == linea.id,
            AgenteLineaAsignacion.es_activa.is_(True),
        ).first()
        if current and current.agente_id != agente.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La linea seleccionada ya esta ocupada")
        if not current:
            db.add(
                AgenteLineaAsignacion(
                    agente_id=agente.id,
                    linea_id=linea.id,
                    es_activa=True,
                    cobro_desde_semana=cobro_desde_semana,
                    cargo_inicial=cargo_inicial,
                )
            )
        asignacion_resumen = {
            "modo": modo,
            "asignada": True,
            "linea_id": linea.id,
            "linea_numero": linea.numero,
        }

    if modo == "auto":
        linea = _choose_free_line_automatically(db, lada_objetivo)
        if linea:
            db.add(
                AgenteLineaAsignacion(
                    agente_id=agente.id,
                    linea_id=linea.id,
                    es_activa=True,
                    cobro_desde_semana=cobro_desde_semana,
                    cargo_inicial=cargo_inicial,
                )
            )
            asignacion_resumen = {
                "modo": modo,
                "asignada": True,
                "linea_id": linea.id,
                "linea_numero": linea.numero,
            }
        else:
            asignacion_resumen = {
                "modo": modo,
                "asignada": False,
                "reason": "No hay lineas libres para asignar",
            }

    _set_agent_lada_preference(db, agente.id, lada_objetivo)

    qr_payload = _refresh_agent_qr_for_state(db, agente)

    db.commit()
    db.refresh(agente)

    return {
        "status": "success",
        "data": {
            "agente_id": agente.id,
            "uuid": agente.uuid,
            "nombre": agente.nombre,
            "alias": (_safe_json_object(agente.datos_adicionales).get("alias") if agente.datos_adicionales else None),
            "display_name": _legacy_agent_display_name(agente.nombre, (_safe_json_object(agente.datos_adicionales).get("alias") if agente.datos_adicionales else None), agente.id),
            "modo_asignacion": modo,
            "asignacion": asignacion_resumen,
            "lineas": _agent_active_lines(db, agente.id),
            "qr": {
                "public_url": qr_payload.get("public_url"),
                "es_qr_seguro": bool(qr_payload.get("es_qr_seguro")),
                "qr_mode": qr_payload.get("qr_mode"),
            },
        },
    }


@router.get("/ladas")
async def listar_ladas(
    search: str | None = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Listar ladas para filtros de asignacion y alta manual."""
    try:
        _sync_ladas_from_legacy_catalog(db)
    except Exception:
        # Si la tabla legacy no existe o no es accesible, mantener operación con catálogo local.
        logger.warning("No se pudo sincronizar catalogo_ladas legado; se usa ladas_catalogo local")

    query = db.query(LadaCatalogo).filter(LadaCatalogo.es_activa.is_(True))
    if search:
        term = f"%{search.strip()}%"
        query = query.filter((LadaCatalogo.codigo.ilike(term)) | (LadaCatalogo.nombre_region.ilike(term)))

    rows = query.order_by(LadaCatalogo.codigo.asc()).all()
    return {
        "status": "success",
        "data": [
            {
                "id": row.id,
                "codigo": row.codigo,
                "nombre_region": row.nombre_region,
                "source": "catalogo_ladas+local",
            }
            for row in rows
        ],
    }


@router.post("/ladas")
async def crear_o_reactivar_lada(
    payload: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Crear o reactivar una lada de catalogo."""
    require_capture_role(current_user)
    codigo = normalize_lada((payload or {}).get("codigo"))
    nombre_region = str((payload or {}).get("nombre_region") or "").strip() or None

    existing = db.query(LadaCatalogo).filter(LadaCatalogo.codigo == codigo).first()
    if existing:
        existing.es_activa = True
        existing.nombre_region = nombre_region
        db.commit()
        db.refresh(existing)
        return {
            "status": "success",
            "data": {
                "id": existing.id,
                "codigo": existing.codigo,
                "nombre_region": existing.nombre_region,
                "reactivada": True,
            },
        }

    row = LadaCatalogo(codigo=codigo, nombre_region=nombre_region, es_activa=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "status": "success",
        "data": {
            "id": row.id,
            "codigo": row.codigo,
            "nombre_region": row.nombre_region,
            "reactivada": False,
        },
    }


@router.get("/lineas")
async def listar_lineas(
    search: str | None = Query(None),
    solo_ocupadas: bool = Query(False),
    estado: str = Query("todas"),
    lada: str | None = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Listar lineas con estado ocupada/libre y agente asignado."""
    _sync_extensions_inventory(db)
    mode = str(estado or "todas").strip().lower()
    if mode not in {"todas", "libres", "ocupadas"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="estado debe ser: todas, libres u ocupadas")

    query = _get_active_line_query(db)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            (LineaTelefonica.numero.ilike(term)) |
            (LineaTelefonica.tipo.ilike(term)) |
            (LineaTelefonica.descripcion.ilike(term))
        )

    lineas = query.order_by(LineaTelefonica.numero.asc()).all()
    assign_map = _active_line_assignments_map(db)
    ladas = db.query(LadaCatalogo).filter(LadaCatalogo.es_activa.is_(True)).all()
    known_codes = [row.codigo for row in ladas]
    data = []
    for linea in lineas:
        resolved_lada = extract_lada_from_number(linea.numero, known_codes)
        if lada and resolved_lada != normalize_lada(lada):
            continue
        assign = assign_map.get(linea.id)
        if mode == "libres" and assign is not None:
            continue
        if mode == "ocupadas" and assign is None:
            continue
        if solo_ocupadas and assign is None:
            continue
        data.append(serialize_linea_operativa(linea, assignment=assign, known_codes=known_codes, synced_prefix=SYNCED_EXTENSION_PREFIX))

    return {"status": "success", "data": data}


@router.post("/lineas")
async def crear_linea(
    payload: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Crear, reactivar o sincronizar una linea operativa."""
    require_capture_role(current_user)
    numero = _safe_line_number((payload or {}).get("numero", ""))
    tipo = str((payload or {}).get("tipo") or "MANUAL").strip().upper() or "MANUAL"
    descripcion = str((payload or {}).get("descripcion") or "").strip() or None
    categoria_linea = normalize_categoria_linea((payload or {}).get("categoria_linea"), default="NO_DEFINIDA")
    estado_conexion = normalize_estado_conexion((payload or {}).get("estado_conexion"), default="DESCONOCIDA")
    fecha_ultimo_uso = parse_fecha_ultimo_uso((payload or {}).get("fecha_ultimo_uso"))
    sincronizar = bool((payload or {}).get("sincronizar", True))

    sync_result = _sync_extensions_inventory(db) if sincronizar else build_empty_line_sync_result()

    row = db.query(LineaTelefonica).filter(LineaTelefonica.numero == numero).first()
    created = False
    reactivated = False
    if row:
        if not row.es_activa:
            row.es_activa = True
            reactivated = True
        if tipo:
            row.tipo = tipo
        if descripcion is not None:
            row.descripcion = descripcion
        row.categoria_linea = categoria_linea
        row.estado_conexion = estado_conexion
        row.fecha_ultimo_uso = fecha_ultimo_uso
        row.fecha_actualizacion = _utcnow()
    else:
        row = LineaTelefonica(
            numero=numero,
            tipo=tipo,
            descripcion=descripcion,
            categoria_linea=categoria_linea,
            estado_conexion=estado_conexion,
            fecha_ultimo_uso=fecha_ultimo_uso,
            es_activa=True,
        )
        db.add(row)
        created = True

    db.commit()
    db.refresh(row)
    return {
        "status": "success",
        "data": {
            **serialize_linea_operativa(row, synced_prefix=SYNCED_EXTENSION_PREFIX),
            "created": created,
            "reactivated": reactivated,
            "sincronizadas": sync_result["source"],
            "ladas_creadas": sync_result.get("ladas_created", 0),
            "ladas_reactivadas": sync_result.get("ladas_reactivated", 0),
        },
    }


@router.put("/lineas/{linea_id}")
async def actualizar_linea(
    linea_id: int,
    payload: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Actualizar metadatos de una linea operativa."""
    require_capture_role(current_user)
    _sync_extensions_inventory(db)

    row = db.query(LineaTelefonica).filter(LineaTelefonica.id == linea_id, LineaTelefonica.es_activa.is_(True)).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linea no encontrada")

    raw_numero = (payload or {}).get("numero")
    new_numero = _safe_line_number(raw_numero) if raw_numero not in (None, "") else row.numero
    tipo = str((payload or {}).get("tipo") or row.tipo or "MANUAL").strip().upper() or "MANUAL"
    descripcion = (payload or {}).get("descripcion")
    categoria_linea = (payload or {}).get("categoria_linea")
    estado_conexion = (payload or {}).get("estado_conexion")
    fecha_ultimo_uso_raw = (payload or {}).get("fecha_ultimo_uso")
    if descripcion is not None:
        descripcion = str(descripcion).strip() or None
    else:
        descripcion = row.descripcion
    if categoria_linea is not None:
        categoria_linea = normalize_categoria_linea(categoria_linea, default="NO_DEFINIDA")
    else:
        categoria_linea = normalize_categoria_linea(row.categoria_linea, default="NO_DEFINIDA")
    if estado_conexion is not None:
        estado_conexion = normalize_estado_conexion(estado_conexion, default="DESCONOCIDA")
    else:
        estado_conexion = normalize_estado_conexion(row.estado_conexion, default="DESCONOCIDA")
    if "fecha_ultimo_uso" in (payload or {}):
        fecha_ultimo_uso = parse_fecha_ultimo_uso(fecha_ultimo_uso_raw)
    else:
        fecha_ultimo_uso = row.fecha_ultimo_uso

    duplicate = db.query(LineaTelefonica).filter(
        LineaTelefonica.numero == new_numero,
        LineaTelefonica.id != linea_id,
    ).first()
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe otra linea con ese numero")

    row.numero = new_numero
    row.tipo = tipo
    row.descripcion = descripcion
    row.categoria_linea = categoria_linea
    row.estado_conexion = estado_conexion
    row.fecha_ultimo_uso = fecha_ultimo_uso
    row.fecha_actualizacion = _utcnow()
    db.commit()
    db.refresh(row)

    return {
        "status": "success",
        "data": serialize_linea_operativa(row, synced_prefix=SYNCED_EXTENSION_PREFIX),
    }


@router.post("/lineas/sync")
async def sincronizar_lineas_pbx(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sincronizar inventario operativo desde registro_agentes.extensions_pbx."""
    require_capture_role(current_user)
    sync_result = _sync_extensions_inventory(db)
    db.commit()
    return {
        "status": "success",
        "message": "Inventario de lineas sincronizado desde extensions_pbx",
        "data": sync_result,
    }


@router.post("/lineas/{linea_id}/asignar")
async def asignar_linea_a_agente(
    linea_id: int,
    payload: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Asignar una linea a un agente y marcarla ocupada."""
    require_capture_role(current_user)
    agente_id = int((payload or {}).get("agente_id") or 0)
    if agente_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debe enviar agente_id")

    _sync_extensions_inventory(db)
    linea = _get_active_line_query(db).filter(
        LineaTelefonica.id == linea_id,
    ).first()
    if not linea:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linea no encontrada")

    agente = db.query(DatoImportado).filter(DatoImportado.id == agente_id, DatoImportado.es_activo.is_(True)).first()
    if not agente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente no encontrado")

    cobro_desde_semana = _parse_week_start((payload or {}).get("cobro_desde_semana"))
    cargo_inicial = _parse_initial_charge((payload or {}).get("cargo_inicial"))

    current = db.query(AgenteLineaAsignacion).filter(
        AgenteLineaAsignacion.linea_id == linea_id,
        AgenteLineaAsignacion.es_activa.is_(True),
    ).first()
    if current and current.agente_id != agente_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La linea ya esta ocupada")
    if current and current.agente_id == agente_id:
        return {"status": "success", "message": "La linea ya estaba asignada a este agente"}

    row = AgenteLineaAsignacion(
        agente_id=agente_id,
        linea_id=linea_id,
        es_activa=True,
        cobro_desde_semana=cobro_desde_semana,
        cargo_inicial=cargo_inicial,
    )
    db.add(row)
    _refresh_agent_qr_for_state(db, agente)
    db.commit()
    db.refresh(row)
    return {
        "status": "success",
        "data": {
            "linea_id": linea.id,
            "linea": linea.numero,
            "agente_id": agente.id,
            "agente": agente.nombre,
            "ocupada": True,
            "cobro_desde_semana": row.cobro_desde_semana.isoformat() if row.cobro_desde_semana else None,
            "cargo_inicial": float(row.cargo_inicial or 0),
        },
    }


@router.post("/lineas/{linea_id}/liberar")
async def liberar_linea(
    linea_id: int,
    payload: dict = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Liberar linea ocupada (deja historial de asignacion)."""
    require_admin_role(current_user, "Solo administradores pueden liberar lineas")
    agente_id = int((payload or {}).get("agente_id") or 0)
    _sync_extensions_inventory(db)

    linea = _get_active_line_query(db).filter(LineaTelefonica.id == linea_id).first()
    if not linea:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linea no encontrada")

    query = db.query(AgenteLineaAsignacion).filter(
        AgenteLineaAsignacion.linea_id == linea_id,
        AgenteLineaAsignacion.es_activa.is_(True),
    )
    if agente_id > 0:
        query = query.filter(AgenteLineaAsignacion.agente_id == agente_id)

    current = query.first()
    if not current:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No hay asignacion activa para liberar")

    current.es_activa = False
    current.fecha_liberacion = _utcnow()
    if current.agente:
        _refresh_agent_qr_for_state(db, current.agente)
    db.commit()
    return {
        "status": "success",
        "data": {
            "linea_id": current.linea_id,
            "agente_id": current.agente_id,
            "ocupada": False,
        },
    }


@router.delete("/lineas/{linea_id}")
async def desactivar_linea(
    linea_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Desactivar una linea del inventario (no elimina historial)."""
    require_admin_role(current_user, "Solo administradores pueden desactivar lineas")
    _sync_extensions_inventory(db)
    linea = _get_active_line_query(db).filter(LineaTelefonica.id == linea_id).first()
    if not linea:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linea no encontrada")

    active_assign = db.query(AgenteLineaAsignacion).filter(
        AgenteLineaAsignacion.linea_id == linea_id,
        AgenteLineaAsignacion.es_activa.is_(True),
    ).first()
    if active_assign:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Primero libera la linea activa")

    linea.es_activa = False
    db.commit()
    return {"status": "success", "data": {"linea_id": linea_id, "es_activa": False}}


@router.get("/config/cuota")
async def obtener_cuota(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Obtener cuota semanal actual."""
    return {"status": "success", "cuota_semanal": get_cuota_semanal(db)}


@router.put("/config/cuota")
async def actualizar_cuota(
    payload: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Actualizar cuota semanal configurable."""
    require_admin_role(current_user, "Solo admin puede modificar cuota")

    cuota = payload.get("cuota_semanal")
    if cuota is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debe enviar cuota_semanal")
    try:
        cuota_value = float(cuota)
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cuota inválida")
    if cuota_value <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La cuota debe ser mayor a 0")

    nueva = set_cuota_semanal(db, cuota_value)
    return {"status": "success", "cuota_semanal": nueva}


@router.post("/alertas/procesar")
async def procesar_alertas_pago(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Procesar alertas de miercoles pendientes (manual)."""
    require_admin_role(current_user, "Solo administradores pueden procesar alertas")
    resultado = generar_alertas_miercoles_pendientes(db)
    return {"status": "success", "data": resultado}


@router.get("/alertas")
async def listar_alertas(
    semana: date | None = Query(None),
    solo_pendientes: bool = Query(True),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Listar alertas de pago emitidas."""
    query = db.query(AlertaPago)
    if semana:
        query = query.filter(AlertaPago.semana_inicio == monday_of_week(semana))
    if solo_pendientes:
        query = query.filter(AlertaPago.atendida.is_(False))

    alertas = query.order_by(AlertaPago.fecha_alerta.desc()).all()
    return {
        "status": "success",
        "data": [
            {
                "id": a.id,
                "agente_id": a.agente_id,
                "semana_inicio": a.semana_inicio.isoformat(),
                "fecha_alerta": a.fecha_alerta.isoformat() if a.fecha_alerta else None,
                "motivo": a.motivo,
                "atendida": a.atendida,
            }
            for a in alertas
        ],
    }


@router.get("/reporte-semanal")
async def reporte_semanal(
    semana: date | None = Query(None),
    agente: str | None = Query(None),
    empresa: str | None = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reporte semanal de pago por agente."""
    data = obtener_reporte_semanal(db, semana, agente_buscar=agente, empresa_buscar=empresa)
    return {"status": "success", **data}


@router.get("/agentes/estado-pago")
async def listar_agentes_extension_estado_pago(
    semana: date | None = Query(None),
    search: str | None = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Vista operativa de agentes con linea activa y estado de pago."""
    activos_operativos = int(
        db.query(DatoImportado)
        .filter(DatoImportado.es_activo.is_(True))
        .count()
    )
    if activos_operativos == 0:
        try:
            _sync_agents_from_legacy_table(db, activate_existing=True, limit=5000)
            db.commit()
        except Exception:
            db.rollback()

    semana_ref = monday_of_week(semana or date.today())
    if semana is None:
        params = {}
        where_sql = ""
        if search:
            where_sql = " WHERE nombre LIKE :term OR extension_numero LIKE :term "
            params["term"] = f"%{search.strip()}%"
        week_label = semana_ref.isoformat()
        try:
            rows = db.execute(
                text(
                    "SELECT * FROM vw_agentes_extensiones_pago_actual"
                    f"{where_sql}"
                    " ORDER BY nombre ASC"
                ),
                params,
            ).mappings().all()
        except Exception:
            fallback_params = {"week_ref": semana_ref}
            fallback_where_parts = []
            if search:
                fallback_where_parts.append("(d.nombre LIKE :term OR l.numero LIKE :term)")
                fallback_params["term"] = f"%{search.strip()}%"
            fallback_where_clause = f" AND {' AND '.join(fallback_where_parts)}" if fallback_where_parts else ""
            rows = db.execute(
                text(
                    """
                    SELECT
                        d.id AS agente_id,
                        d.uuid,
                        d.nombre,
                        COALESCE(d.es_activo, 1) AS es_activo,
                        l.id AS linea_id,
                        l.numero AS extension_numero,
                        l.tipo AS extension_tipo,
                        CASE
                            WHEN ala.id IS NULL OR l.id IS NULL THEN 'SIN_LINEA'
                            ELSE 'ASIGNADA'
                        END AS linea_estado,
                        p.semana_inicio,
                        COALESCE(p.pagado, 0) AS pagado_semana,
                        COALESCE(p.monto, 0) AS monto_semana,
                        p.fecha_pago,
                        CASE
                            WHEN p.id IS NULL OR COALESCE(p.pagado, 0) = 0 THEN 'Pendiente de Pago'
                            ELSE 'Al Corriente'
                        END AS estado_pago
                    FROM datos_importados d
                    LEFT JOIN agente_linea_asignaciones ala
                        ON ala.agente_id = d.id AND ala.es_activa = 1
                    LEFT JOIN lineas_telefonicas l
                        ON l.id = ala.linea_id AND COALESCE(l.es_activa, 1) = 1
                    LEFT JOIN pagos_semanales p
                        ON p.agente_id = d.id AND p.semana_inicio = :week_ref
                    WHERE COALESCE(d.es_activo, 1) = 1
                    """
                    + fallback_where_clause
                    + " ORDER BY d.nombre ASC"
                ),
                fallback_params,
            ).mappings().all()
    else:
        params = {"week_ref": semana_ref}
        where_parts = []
        if search:
            where_parts.append("(d.nombre LIKE :term OR l.numero LIKE :term)")
            params["term"] = f"%{search.strip()}%"
        where_clause = f" AND {' AND '.join(where_parts)}" if where_parts else ""
        rows = db.execute(
            text(
                """
                SELECT
                    d.id AS agente_id,
                    d.uuid,
                    d.nombre,
                    COALESCE(d.es_activo, 1) AS es_activo,
                    l.id AS linea_id,
                    l.numero AS extension_numero,
                    l.tipo AS extension_tipo,
                    CASE
                        WHEN ala.id IS NULL OR l.id IS NULL THEN 'SIN_LINEA'
                        ELSE 'ASIGNADA'
                    END AS linea_estado,
                    p.semana_inicio,
                    COALESCE(p.pagado, 0) AS pagado_semana,
                    COALESCE(p.monto, 0) AS monto_semana,
                    p.fecha_pago,
                    CASE
                        WHEN p.id IS NULL OR COALESCE(p.pagado, 0) = 0 THEN 'Pendiente de Pago'
                        ELSE 'Al Corriente'
                    END AS estado_pago
                FROM datos_importados d
                LEFT JOIN agente_linea_asignaciones ala
                    ON ala.agente_id = d.id AND ala.es_activa = 1
                LEFT JOIN lineas_telefonicas l
                    ON l.id = ala.linea_id AND COALESCE(l.es_activa, 1) = 1
                LEFT JOIN pagos_semanales p
                    ON p.agente_id = d.id AND p.semana_inicio = :week_ref
                WHERE COALESCE(d.es_activo, 1) = 1
                """
                + where_clause
                + " ORDER BY d.nombre ASC"
            ),
            params,
        ).mappings().all()
        week_label = semana_ref.isoformat()

    status_cache: dict[int, dict] = {}
    agente_ids = {
        int(row.get("agente_id"))
        for row in rows
        if row.get("agente_id") is not None
    }
    agentes = (
        db.query(DatoImportado)
        .filter(DatoImportado.id.in_(agente_ids), DatoImportado.es_activo.is_(True))
        .all()
        if agente_ids
        else []
    )
    agentes_by_id = {int(a.id): a for a in agentes}
    for agente_id in agente_ids:
        agente = agentes_by_id.get(agente_id)
        if not agente:
            continue
        try:
            resumen = resumen_cobranza_agente(db, agente, semana_ref)
            saldo_acumulado = float(resumen.get("saldo_acumulado") or 0.0)
            pendiente = saldo_acumulado > 0.009
            status_cache[agente_id] = {
                "saldo_acumulado": saldo_acumulado,
                "semanas_pendientes": int(resumen.get("semanas_pendientes") or 0),
                "pagado": not pendiente,
                "estado_pago": "Pendiente de Pago" if pendiente else "Al Corriente",
            }
        except Exception:
            logger.exception("No se pudo calcular resumen de cobranza para agente_id=%s", agente_id)

    data = []
    for row in rows:
        agente_id = row.get("agente_id")
        cached = status_cache.get(int(agente_id)) if agente_id is not None else None
        raw_week = row.get("semana_inicio")
        if raw_week is None:
            semana_inicio = week_label
        elif hasattr(raw_week, "isoformat"):
            semana_inicio = raw_week.isoformat()
        else:
            semana_inicio = str(raw_week)

        saldo_row = float(row.get("deuda_acumulada") or row.get("deuda") or 0.0)
        pendiente_row = saldo_row > 0.009 or not bool(row.get("pagado_semana"))
        raw_fecha_pago = row.get("fecha_pago")
        if raw_fecha_pago is None:
            fecha_pago = None
        elif hasattr(raw_fecha_pago, "isoformat"):
            fecha_pago = raw_fecha_pago.isoformat()
        else:
            fecha_pago = str(raw_fecha_pago)

        data.append({
            "agente_id": agente_id,
            "uuid": row.get("uuid"),
            "nombre": row.get("nombre"),
            "linea_id": row.get("linea_id"),
            "extension_numero": row.get("extension_numero"),
            "extension_tipo": row.get("extension_tipo"),
            "linea_estado": row.get("linea_estado") or ("ASIGNADA" if row.get("linea_id") else "SIN_LINEA"),
            "semana_inicio": semana_inicio,
            "pagado": bool(cached.get("pagado")) if cached else (not pendiente_row),
            "monto": float(row.get("monto_semana") or 0),
            "saldo_acumulado": float(cached.get("saldo_acumulado")) if cached else saldo_row,
            "semanas_pendientes": int(cached.get("semanas_pendientes")) if cached else 0,
            "fecha_pago": fecha_pago,
            "estado_pago": cached.get("estado_pago") if cached else (row.get("estado_pago") or "Pendiente de Pago"),
        })

    return {
        "status": "success",
        "semana_inicio": week_label,
        "data": data,
    }


@router.get("/agentes/sin-linea")
async def listar_agentes_sin_linea(
    search: str | None = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Listar agentes activos sin línea telefónica activa asignada."""
    # Subquery: IDs de agentes que tienen asignación activa con línea activa
    subq = (
        select(AgenteLineaAsignacion.agente_id)
        .join(
            LineaTelefonica,
            (LineaTelefonica.id == AgenteLineaAsignacion.linea_id)
            & (LineaTelefonica.es_activa.is_(True)),
        )
        .where(AgenteLineaAsignacion.es_activa.is_(True))
    )

    query = db.query(DatoImportado).filter(
        DatoImportado.es_activo.isnot(False),
        ~DatoImportado.id.in_(subq),
    )

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            DatoImportado.nombre.ilike(term)
            | DatoImportado.telefono.ilike(term)
        )

    agentes = query.order_by(DatoImportado.nombre.asc()).limit(500).all()

    data = [
        {
            "id": ag.id,
            "uuid": ag.uuid,
            "nombre": ag.nombre,
            "telefono": ag.telefono,
            "tiene_qr": bool(ag.qr_filename),
            "qr_filename": ag.qr_filename,
        }
        for ag in agentes
    ]

    return {"status": "success", "total": len(data), "data": data}


@router.get("/agentes/estado")
async def listar_agentes_estado(
    search: str | None = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Listar agentes activos y su estado de línea (asignada o sin asignar).
    Incluye estado de QR para facilitar la gestión masiva.
    """
    params: dict = {}
    search_clause = ""
    if search:
        search_clause = " AND (d.nombre LIKE :term OR d.telefono LIKE :term) "
        params["term"] = f"%{search.strip()}%"

    rows = db.execute(
        text(
            f"""
            SELECT
                d.id,
                d.uuid,
                d.nombre,
                d.telefono,
                d.datos_adicionales,
                CASE WHEN d.qr_filename IS NOT NULL AND d.qr_filename <> '' THEN 1 ELSE 0 END AS tiene_qr,
                d.qr_filename,
                d.fecha_creacion,
                COUNT(DISTINCT l.id) AS lineas_count,
                GROUP_CONCAT(DISTINCT l.numero ORDER BY l.numero SEPARATOR ', ') AS lineas_numeros,
                CASE
                    WHEN COUNT(DISTINCT l.id) > 0 THEN 'ASIGNADA'
                    ELSE 'SIN_LINEA'
                END AS linea_estado
            FROM datos_importados d
            LEFT JOIN agente_linea_asignaciones ala
                ON ala.agente_id = d.id AND ala.es_activa = 1
            LEFT JOIN lineas_telefonicas l
                ON l.id = ala.linea_id AND COALESCE(l.es_activa, 1) = 1
            WHERE COALESCE(d.es_activo, 1) = 1
              {search_clause}
            GROUP BY d.id, d.uuid, d.nombre, d.telefono, d.datos_adicionales, d.qr_filename, d.fecha_creacion
            ORDER BY d.nombre ASC
            LIMIT 500
            """
        ),
        params,
    ).mappings().all()

    data = []
    for row in rows:
        extras = _safe_json_object(row.get("datos_adicionales"))
        created = row.get("fecha_creacion")
        if hasattr(created, "isoformat"):
            created_value = created.isoformat()
        elif created is not None:
            created_value = str(created)
        else:
            created_value = None
        data.append(
            {
                "id": int(row.get("id") or 0),
                "uuid": row.get("uuid"),
                "nombre": row.get("nombre") or f"Agente {row.get('id')}",
                "telefono": row.get("telefono"),
                "alias": extras.get("alias"),
                "tiene_qr": bool(int(row.get("tiene_qr") or 0)),
                "qr_filename": row.get("qr_filename"),
                "fecha_creacion": created_value,
                "lineas_count": int(row.get("lineas_count") or 0),
                "lineas_numeros": row.get("lineas_numeros") or "",
                "linea_estado": row.get("linea_estado") or ("ASIGNADA" if int(row.get("lineas_count") or 0) > 0 else "SIN_LINEA"),
            }
        )

    return {
        "status": "success",
        "total": len(data),
        "data": data,
    }


@router.post("/agentes/generar-qr-masivo")
async def generar_qr_masivo_sin_qr(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Genera QR para todos los agentes activos que aún no tienen uno.
    El QR generado es tipo UUID-fallback (seguro si el agente tiene línea activa).
    Requiere rol de captura o superior.
    """
    require_capture_role(current_user)

    agentes_sin_qr = (
        db.query(DatoImportado)
        .filter(
            DatoImportado.es_activo.is_(True),
            (DatoImportado.qr_filename.is_(None) | (DatoImportado.qr_filename == "")),
        )
        .all()
    )

    generados = 0
    errores: list[dict] = []

    for agente in agentes_sin_qr:
        try:
            _refresh_agent_qr_for_state(db, agente, request=request)
            generados += 1
        except Exception as exc:
            errores.append(
                {
                    "agente_id": agente.id,
                    "nombre": agente.nombre,
                    "error": str(exc),
                }
            )

    if generados > 0:
        db.commit()

    return {
        "status": "success",
        "total_sin_qr": len(agentes_sin_qr),
        "generados": generados,
        "errores": errores,
    }


@router.get("/agentes/sin-imprimir")
async def listar_agentes_sin_imprimir(
    solo_activos: bool = Query(True),
    estado: str = Query("sin_imprimir", description="sin_imprimir | impresos | todos"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Agentes con QR generado.

    estado=sin_imprimir (default): solo los que no han sido impresos.
    estado=impresos: solo los ya impresos.
    estado=todos: todos los que tienen QR generado.
    """
    require_capture_role(current_user)
    query = db.query(DatoImportado).filter(
        DatoImportado.qr_code.isnot(None),
    )
    if estado == "sin_imprimir":
        query = query.filter(DatoImportado.qr_impreso.is_(False))
    elif estado == "impresos":
        query = query.filter(DatoImportado.qr_impreso.is_(True))
    # estado="todos" => no extra filter
    if solo_activos:
        query = query.filter(DatoImportado.es_activo.is_(True))
    agentes = query.order_by(DatoImportado.nombre.asc()).all()
    result = []
    for a in agentes:
        extras = _safe_json_object(a.datos_adicionales)
        result.append({
            "id": a.id,
            "nombre": a.nombre,
            "alias": extras.get("alias") if isinstance(extras, dict) else None,
            "telefono": a.telefono,
            "estatus_codigo": a.estatus_codigo,
            "fecha_creacion": a.fecha_creacion.isoformat() if a.fecha_creacion else None,
            "qr_impreso": bool(a.qr_impreso),
            "qr_impreso_at": a.qr_impreso_at.isoformat() if a.qr_impreso_at else None,
        })
    return {"total": len(result), "agentes": result}


@router.post("/agentes/marcar-impreso")
async def marcar_agentes_impreso(
    payload: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Marcar/desmarcar agentes como impresos.

    Body JSON: {"ids": [1,2,3], "impreso": true}
    """
    require_capture_role(current_user)
    ids = payload.get("ids") or []
    impreso = bool(payload.get("impreso", True))
    if not isinstance(ids, list) or not ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Se requiere 'ids' como lista no vacía")
    validated_ids = []
    for raw_id in ids:
        try:
            validated_ids.append(int(raw_id))
        except (TypeError, ValueError):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"ID inválido: {raw_id}")
    if len(validated_ids) > 500:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Máximo 500 IDs por solicitud")
    now = _utcnow()
    updated = db.query(DatoImportado).filter(DatoImportado.id.in_(validated_ids)).all()
    for agente in updated:
        agente.qr_impreso = impreso
        agente.qr_impreso_at = now if impreso else None
    db.commit()
    return {"actualizados": len(updated), "impreso": impreso}


@router.get("/agentes/export/pdf")
async def exportar_qr_agentes_pdf(
    request: Request,
    ids_csv: str | None = Query(None, description="IDs de agentes separados por coma"),
    search: str | None = Query(None, description="Filtro parcial por nombre o telefono"),
    layout: str = Query("sheet", pattern="^(sheet|labels|oficio)$"),
    solo_activos: bool = Query(True),
    marcar_impreso: bool = Query(True, description="Marcar agentes exportados como impresos"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Exportar QRs estaticos de agentes en PDF listo para hoja o etiquetas."""
    require_capture_role(current_user)

    query = db.query(DatoImportado)
    if solo_activos:
        query = query.filter(DatoImportado.es_activo.is_(True))

    agent_ids: list[int] = []
    if ids_csv:
        for raw in str(ids_csv).split(","):
            value = raw.strip()
            if not value:
                continue
            if not value.isdigit():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"ID de agente invalido: {value}")
            agent_ids.append(int(value))

    if agent_ids:
        query = query.filter(DatoImportado.id.in_(agent_ids))

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            (DatoImportado.nombre.ilike(term)) |
            (DatoImportado.telefono.ilike(term)) |
            (DatoImportado.email.ilike(term))
        )

    agentes = query.order_by(DatoImportado.nombre.asc(), DatoImportado.id.asc()).limit(500).all()
    if not agentes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No se encontraron agentes para exportar")

    export_rows: list[dict] = []
    for agente in agentes:
        payload = _refresh_agent_qr_for_state(db, agente, request=request)
        extras = _safe_json_object(agente.datos_adicionales)
        export_rows.append(
            {
                "id": agente.id,
                "alias": (extras.get("alias") if isinstance(extras, dict) else None),
                "uuid": agente.uuid,
                "nombre": agente.nombre,
                "telefono": agente.telefono,
                "linea_activa": (payload.get("linea_activa") or {}).get("numero"),
                "linea_estado": payload.get("linea_estado") or "sin_linea",
                "public_url": payload.get("public_url"),
                "qr_path": payload.get("qr_path"),
            }
        )

    db.commit()
    pdf_bytes = build_agent_qr_pdf(export_rows, layout=layout)

    if marcar_impreso:
        now = _utcnow()
        for agente in agentes:
            agente.qr_impreso = True
            agente.qr_impreso_at = now
        db.commit()

    filename = f"agentes_qr_{layout}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(iter([pdf_bytes]), media_type="application/pdf", headers=headers)


@router.get("/recibos")
async def listar_recibos_pago(
    agente_id: int | None = Query(None),
    include_expired: bool = Query(False),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Listar recibos persistidos para reimpresion."""
    _cleanup_expired_receipts(db)
    db.commit()
    query = db.query(ReciboPago)
    if agente_id:
        query = query.filter(ReciboPago.agente_id == agente_id)
    if not include_expired:
        query = query.filter(ReciboPago.expira_en >= _utcnow())

    rows = query.order_by(ReciboPago.generado_en.desc()).limit(300).all()
    data = []
    for row in rows:
        payload = _safe_json_object(row.contenido_json)
        data.append({
            "token": row.token_recibo,
            "agente_id": row.agente_id,
            "agente_nombre": payload.get("agente_nombre"),
            "linea_numero": row.linea_numero,
            "semana_inicio": payload.get("semana_inicio"),
            "monto": payload.get("monto"),
            "pagado": bool(payload.get("pagado", False)),
            "fecha_pago": payload.get("fecha_pago"),
            "generado_en": row.generado_en.isoformat() if row.generado_en else None,
            "expira_en": row.expira_en.isoformat() if row.expira_en else None,
            "impresiones": int(row.impresiones_count or 0),
        })
    return {"status": "success", "data": data}


@router.get("/recibos/{token_recibo}")
async def obtener_recibo_pago(
    token_recibo: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Obtener recibo puntual para mostrar/reimprimir."""
    _cleanup_expired_receipts(db)
    row = db.query(ReciboPago).filter(ReciboPago.token_recibo == token_recibo).first()
    if not row:
        db.commit()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recibo no encontrado")
    if row.expira_en < _utcnow():
        db.delete(row)
        db.commit()
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Recibo expirado")

    row.impresiones_count = int(row.impresiones_count or 0) + 1
    row.ultima_impresion = _utcnow()
    db.commit()
    payload = _safe_json_object(row.contenido_json)
    return {
        "status": "success",
        "data": {
            **payload,
            "token": row.token_recibo,
            "linea_numero": row.linea_numero,
            "generado_en": row.generado_en.isoformat() if row.generado_en else None,
            "expira_en": row.expira_en.isoformat() if row.expira_en else None,
            "impresiones": int(row.impresiones_count or 0),
            "ultima_impresion": row.ultima_impresion.isoformat() if row.ultima_impresion else None,
        },
    }


@router.post("/backup")
async def generar_respaldo_manual(
    payload: dict | None = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generar respaldo semanal manual de la base de datos."""
    require_admin_role(current_user, "Solo admin puede generar respaldo")
    backup_dir = (payload or {}).get("backup_dir")
    result = create_weekly_backup(db, force=True, backup_dir=backup_dir)
    if result.get("status") == "error":
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result.get("reason"))
    return {"status": "success", "data": result}


@router.get("/backup/config")
async def obtener_configuracion_respaldo(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Consultar ruta configurada de respaldos."""
    require_admin_role(current_user, "Solo admin puede consultar la configuración de respaldos")
    return {"status": "success", "data": get_backup_settings(db)}


@router.put("/backup/config")
async def actualizar_configuracion_respaldo(
    payload: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Guardar ruta persistente de respaldos."""
    require_admin_role(current_user, "Solo admin puede modificar la configuración de respaldos")
    backup_dir = str((payload or {}).get("backup_dir") or "").strip()
    if not backup_dir:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debes indicar una ruta de respaldo")
    create_if_missing = bool((payload or {}).get("create_if_missing", True))
    try:
        data = set_backup_dir(db, backup_dir, create_if_missing=create_if_missing)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"status": "success", "data": data}


@router.get("/backups")
async def listar_respaldos(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Listar respaldos disponibles."""
    return {"status": "success", "data": list_backups(db=db)}


@router.post("/restore")
async def restaurar_respaldo(
    payload: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Restaurar un respaldo seleccionado."""
    require_admin_role(current_user, "Solo admin puede restaurar respaldos")
    filename = payload.get("filename")
    if not filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debe enviar filename")
    result = restore_backup(db, filename)
    if result.get("status") == "error":
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result.get("reason"))
    return {"status": "success", "data": result}


@router.get("/agente/{agente_id}/qr")
async def obtener_qr_agente(
    agente_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Obtener QR por agente: seguro con linea activa, fallback UUID si aun no tiene linea."""
    agente = db.query(DatoImportado).filter(
        DatoImportado.id == agente_id,
        DatoImportado.es_activo.is_(True)
    ).first()
    if not agente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente no encontrado")

    payload = _refresh_agent_qr_for_state(db, agente, request=request)
    db.commit()

    return {"status": "success", "data": payload}


@router.get("/agente/{agente_id}/qr/download")
async def descargar_qr_agente(
    agente_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Descargar PNG del QR individual del agente."""
    result = await obtener_qr_agente(agente_id, request=request, current_user=current_user, db=db)
    path = (result.get("data") or {}).get("qr_path")
    if not path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QR no disponible")
    return FileResponse(path, media_type="image/png", filename=os.path.basename(path))


@router.get("/public/verify-secure/{token}", response_class=HTMLResponse)
async def verificar_publico_qr_seguro(
    token: str,
    semana: date | None = Query(None),
    db: Session = Depends(get_db),
):
    """Verificacion publica de QR firmado y ligado a agente + linea activa."""
    agente, linea, _payload = _validate_secure_qr_token(db, token, require_current=True)

    semana_ref = monday_of_week(semana or date.today())
    pago = db.query(PagoSemanal).filter(
        PagoSemanal.agente_id == agente.id,
        PagoSemanal.semana_inicio == semana_ref,
    ).first()
    resumen = resumen_cobranza_agente(db, agente, semana_ref)
    app_url = config.get_public_base_url()
    pago_url = f"{app_url}/?section=qr&agente_id={agente.id}&semana={semana_ref.isoformat()}&autoverify=1"

    payload = {
        "status": "success",
        "agente": {
            "id": agente.id,
            "uuid": agente.uuid,
            "nombre": agente.nombre,
            "telefono": agente.telefono,
            "tiene_asignacion": True,
            "linea": linea.numero if linea else None,
        },
        "semana_inicio": semana_ref.isoformat(),
        "pagado": bool(pago.pagado) if pago else False,
        "monto": float(pago.monto) if pago else 0.0,
        "fecha_pago": pago.fecha_pago.isoformat() if pago and pago.fecha_pago else None,
        "deuda_total": float(resumen["deuda_total"]),
        "total_abonado": float(resumen["total_abonado"]),
        "saldo_acumulado": float(resumen["saldo_acumulado"]),
        "semanas_pendientes": int(resumen["semanas_pendientes"]),
        "pago_url": pago_url,
    }
    return _render_public_status_page(payload)


@router.get("/public/verify/{uuid}", response_class=HTMLResponse)
@router.get("/public/verify-uuid/{uuid}", response_class=HTMLResponse)
async def verificar_publico_por_uuid(
    uuid: str,
    semana: date | None = Query(None),
    db: Session = Depends(get_db),
):
    """Verificacion publica para escaneo QR por UUID de agente."""
    agente = db.query(DatoImportado).filter(
        DatoImportado.uuid == uuid,
        DatoImportado.es_activo.is_(True)
    ).first()
    if not agente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente no encontrado")

    semana_ref = monday_of_week(semana or date.today())
    active_assignment = _active_assignment_for_agent(db, agente.id)
    linea = active_assignment.linea if active_assignment and active_assignment.linea and active_assignment.linea.es_activa else None
    pago = db.query(PagoSemanal).filter(
        PagoSemanal.agente_id == agente.id,
        PagoSemanal.semana_inicio == semana_ref
    ).first()
    resumen = resumen_cobranza_agente(db, agente, semana_ref)
    app_url = config.get_public_base_url()
    pago_url = f"{app_url}/?section=qr&agente_id={agente.id}&semana={semana_ref.isoformat()}&autoverify=1"

    payload = {
        "status": "success",
        "agente": {
            "id": agente.id,
            "uuid": agente.uuid,
            "nombre": agente.nombre,
            "telefono": agente.telefono,
            "tiene_asignacion": bool(linea),
            "linea": linea.numero if linea else None,
            "linea_estado": "asignada" if linea else "sin_linea",
        },
        "semana_inicio": semana_ref.isoformat(),
        "pagado": bool(pago.pagado) if pago else False,
        "monto": float(pago.monto) if pago else 0.0,
        "fecha_pago": pago.fecha_pago.isoformat() if pago and pago.fecha_pago else None,
        "deuda_total": float(resumen["deuda_total"]),
        "total_abonado": float(resumen["total_abonado"]),
        "saldo_acumulado": float(resumen["saldo_acumulado"]),
        "semanas_pendientes": int(resumen["semanas_pendientes"]),
        "pago_url": pago_url,
    }
    return _render_public_status_page(payload)


@router.get("/public/verify-by-id/{agente_id}", response_class=HTMLResponse)
async def verificar_publico_por_id(
    agente_id: int,
    semana: date | None = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verificacion por ID restringida para reducir riesgo de enumeracion externa."""
    require_admin_role(current_user, "Solo administradores pueden verificar por ID")
    agente = db.query(DatoImportado).filter(
        DatoImportado.id == agente_id,
        DatoImportado.es_activo.is_(True)
    ).first()
    if not agente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente no encontrado")

    semana_ref = monday_of_week(semana or date.today())
    active_assignment = _active_assignment_for_agent(db, agente.id)
    linea = active_assignment.linea if active_assignment and active_assignment.linea and active_assignment.linea.es_activa else None
    pago = db.query(PagoSemanal).filter(
        PagoSemanal.agente_id == agente.id,
        PagoSemanal.semana_inicio == semana_ref
    ).first()
    resumen = resumen_cobranza_agente(db, agente, semana_ref)
    app_url = config.get_public_base_url()
    pago_url = f"{app_url}/?section=qr&agente_id={agente.id}&semana={semana_ref.isoformat()}&autoverify=1"

    payload = {
        "status": "success",
        "agente": {
            "id": agente.id,
            "uuid": agente.uuid,
            "nombre": agente.nombre,
            "telefono": agente.telefono,
            "tiene_asignacion": bool(linea),
            "linea": linea.numero if linea else None,
            "linea_estado": "asignada" if linea else "sin_linea",
        },
        "semana_inicio": semana_ref.isoformat(),
        "pagado": bool(pago.pagado) if pago else False,
        "monto": float(pago.monto) if pago else 0.0,
        "fecha_pago": pago.fecha_pago.isoformat() if pago and pago.fecha_pago else None,
        "deuda_total": float(resumen["deuda_total"]),
        "total_abonado": float(resumen["total_abonado"]),
        "saldo_acumulado": float(resumen["saldo_acumulado"]),
        "semanas_pendientes": int(resumen["semanas_pendientes"]),
        "pago_url": pago_url,
    }
    return _render_public_status_page(payload)
