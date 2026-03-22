"""Endpoints de verificacion QR para agentes y pagos semanales."""

from datetime import date, datetime, timedelta
import json
import logging
import os
import re
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, FileResponse
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
)
from app.schemas import PagoSemanalCrear, PagoSemanalRespuesta
from app.security import get_current_user
from app.qr import QRGenerator
from app.config import config
from app.utils.backups import (
    create_weekly_backup,
    get_backup_settings,
    list_backups,
    restore_backup,
    set_backup_dir,
)
from app.utils.pagos import (
    generar_alertas_miercoles_pendientes,
    get_cuota_semanal,
    monday_of_week,
    obtener_reporte_semanal,
    set_cuota_semanal,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/qr", tags=["QR Verificacion"])

UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def _render_public_status_page(payload: dict) -> HTMLResponse:
    """Render a public green/red verification page for scanned QR codes."""
    agente = payload.get("agente", {})
    pagado = bool(payload.get("pagado", False))
    asignado = bool(agente.get("tiene_asignacion", False))
    color = "#16966a" if pagado else "#d64545"
    label = "PAGADO" if pagado else "PENDIENTE"
    asignacion = "NUMERO ASIGNADO" if asignado else "SIN NUMERO ASIGNADO"
    html = f"""
    <!doctype html>
    <html lang=\"es\">
    <head>
        <meta charset=\"utf-8\">
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
        <title>Verificación de Pago</title>
        <style>
            body {{ font-family: Segoe UI, Arial, sans-serif; margin: 0; background: #f4f7fb; color: #1a2330; }}
            .wrap {{ max-width: 760px; margin: 40px auto; padding: 20px; }}
            .card {{ background: #fff; border-radius: 18px; box-shadow: 0 12px 30px rgba(0,0,0,.10); overflow: hidden; }}
            .hero {{ background: {color}; color: #fff; padding: 28px; text-align: center; }}
            .hero h1 {{ margin: 0; font-size: 2rem; }}
            .badge {{ display: inline-block; margin-top: 12px; padding: 8px 18px; border-radius: 999px; background: rgba(255,255,255,.18); font-weight: 700; }}
            .body {{ padding: 24px; font-size: 1rem; line-height: 1.6; }}
            .row {{ margin-bottom: 10px; }}
            .label {{ font-weight: 700; }}
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
                    <div class=\"row\"><span class=\"label\">Teléfono:</span> {agente.get('telefono', '-')}</div>
                    <div class=\"row\"><span class=\"label\">Asignación:</span> {asignacion}</div>
                    <div class=\"row\"><span class=\"label\">Semana:</span> {payload.get('semana_inicio', '-')}</div>
                    <div class=\"row\"><span class=\"label\">Monto:</span> ${float(payload.get('monto', 0.0)):.2f} MXN</div>
                    <div class=\"row\"><span class=\"label\">Fecha de pago:</span> {payload.get('fecha_pago') or 'Sin registro'}</div>
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


def _has_assignment(dato: DatoImportado) -> bool:
    return bool((dato.telefono or '').strip() or (_extract_voip(dato) or '').strip())


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


def _normalize_lada(raw: str) -> str:
    value = re.sub(r"\D", "", str(raw or "").strip())
    if len(value) < 2 or len(value) > 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lada invalida")
    return value


def _extract_lada_from_number(number: str, known_codes: list[str]) -> str | None:
    digits = re.sub(r"\D", "", str(number or ""))
    if not digits:
        return None
    # Match longest known lada prefix first.
    for code in sorted((c for c in known_codes if c), key=len, reverse=True):
        if digits.startswith(code):
            return code
    # Fallback for unknown catalog: first 3 digits for MX style dialing.
    return digits[:3] if len(digits) >= 3 else digits


def _resolve_or_create_line_for_manual_assignment(db: Session, payload: dict) -> LineaTelefonica:
    linea_id = int((payload or {}).get("linea_id") or 0)
    if linea_id > 0:
        linea = db.query(LineaTelefonica).filter(
            LineaTelefonica.id == linea_id,
            LineaTelefonica.es_activa.is_(True),
        ).first()
        if not linea:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linea no encontrada")
        return linea

    raw_number = (payload or {}).get("numero_linea_manual")
    numero = _safe_line_number(raw_number)
    tipo = str((payload or {}).get("tipo_linea") or "VOIP").strip().upper()[:30] or "VOIP"
    descripcion = str((payload or {}).get("descripcion_linea") or "").strip() or None

    existing = db.query(LineaTelefonica).filter(LineaTelefonica.numero == numero).first()
    if existing:
        existing.es_activa = True
        if tipo:
            existing.tipo = tipo
        if descripcion is not None:
            existing.descripcion = descripcion
        db.flush()
        return existing

    line = LineaTelefonica(numero=numero, tipo=tipo, descripcion=descripcion, es_activa=True)
    db.add(line)
    db.flush()
    return line


def _choose_free_line_automatically(db: Session, lada_objetivo: str | None = None) -> LineaTelefonica | None:
    active_assignments = _active_line_assignments_map(db)
    lineas = db.query(LineaTelefonica).filter(LineaTelefonica.es_activa.is_(True)).order_by(LineaTelefonica.numero.asc()).all()
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
    lada_code = _normalize_lada(lada_code)
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


@router.post("/pagos", response_model=PagoSemanalRespuesta)
async def registrar_pago_semanal(
    pago_in: PagoSemanalCrear,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Registrar o actualizar pago semanal por agente/número."""
    agente = db.query(DatoImportado).filter(
        DatoImportado.id == pago_in.agente_id,
        DatoImportado.es_activo.is_(True)
    ).first()
    if not agente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente no encontrado")

    semana = monday_of_week(pago_in.semana_inicio)
    monto_final = pago_in.monto if pago_in.monto and pago_in.monto > 0 else get_cuota_semanal(db)
    pago = db.query(PagoSemanal).filter(
        PagoSemanal.agente_id == pago_in.agente_id,
        PagoSemanal.semana_inicio == semana
    ).first()

    if not pago:
        pago = PagoSemanal(
            agente_id=pago_in.agente_id,
            telefono=pago_in.telefono,
            numero_voip=pago_in.numero_voip,
            semana_inicio=semana,
            monto=monto_final,
            pagado=pago_in.pagado,
            fecha_pago=datetime.utcnow() if pago_in.pagado else None,
            observaciones=pago_in.observaciones,
        )
        db.add(pago)
    else:
        pago.telefono = pago_in.telefono
        pago.numero_voip = pago_in.numero_voip
        pago.monto = monto_final
        pago.pagado = pago_in.pagado
        pago.observaciones = pago_in.observaciones
        pago.fecha_pago = datetime.utcnow() if pago_in.pagado else None

    if pago_in.pagado:
        alertas = db.query(AlertaPago).filter(
            AlertaPago.agente_id == pago_in.agente_id,
            AlertaPago.semana_inicio == semana,
            AlertaPago.atendida.is_(False)
        ).all()
        for alerta in alertas:
            alerta.atendida = True
            alerta.fecha_atendida = datetime.utcnow()

    db.commit()
    db.refresh(pago)

    logger.info("Usuario %s registró pago semanal para agente %s", current_user.get("username"), pago_in.agente_id)
    return pago


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
    lineas_agente = _agent_active_lines(db, agente.id)
    tiene_asignacion = _has_assignment(agente) or bool(lineas_agente)

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
            "cuota_semanal": get_cuota_semanal(db),
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
            (DatoImportado.empresa.ilike(term))
        )

    agentes = query.order_by(DatoImportado.nombre.asc()).limit(500).all()
    return {
        "status": "success",
        "data": [
            {
                "id": a.id,
                "uuid": a.uuid,
                "nombre": a.nombre,
                "telefono": a.telefono,
                "empresa": a.empresa,
                "datos_adicionales": _safe_json_object(a.datos_adicionales),
                "ladas_preferidas": [
                    pref.lada.codigo for pref in sorted(a.ladas_preferidas, key=lambda x: x.prioridad) if pref.lada and pref.lada.es_activa
                ],
                "lineas": _agent_active_lines(db, a.id),
            }
            for a in agentes
        ],
    }


@router.post("/agentes/manual")
async def crear_agente_manual(
    payload: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Crear agente manualmente y asignar linea de forma opcional."""
    nombre = str((payload or {}).get("nombre") or "").strip()
    if not nombre:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nombre es requerido")

    telefono = str((payload or {}).get("telefono") or "").strip() or None
    email = str((payload or {}).get("email") or "").strip() or None
    empresa = str((payload or {}).get("empresa") or "").strip() or None
    ciudad = str((payload or {}).get("ciudad") or "").strip() or None
    pais = str((payload or {}).get("pais") or "").strip() or None

    datos_adicionales = {
        "alias": str((payload or {}).get("alias") or "").strip() or None,
        "ubicacion": str((payload or {}).get("ubicacion") or "").strip() or None,
        "fp": str((payload or {}).get("fp") or "").strip() or None,
        "fc": str((payload or {}).get("fc") or "").strip() or None,
        "grupo": str((payload or {}).get("grupo") or "").strip() or None,
        "numero_voip": str((payload or {}).get("numero_voip") or "").strip() or None,
    }
    datos_adicionales = {k: v for k, v in datos_adicionales.items() if v not in (None, "")}

    modo = str((payload or {}).get("modo_asignacion") or "ninguna").strip().lower()
    if modo not in {"ninguna", "manual", "auto"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="modo_asignacion invalido")

    lada_objetivo = str((payload or {}).get("lada_objetivo") or "").strip() or None
    if lada_objetivo:
        lada_objetivo = _normalize_lada(lada_objetivo)

    agente = DatoImportado(
        nombre=nombre,
        email=email,
        telefono=telefono,
        empresa=empresa,
        ciudad=ciudad,
        pais=pais,
        datos_adicionales=json.dumps(datos_adicionales, ensure_ascii=False) if datos_adicionales else None,
        creado_por=current_user.get("id"),
        es_activo=True,
    )
    db.add(agente)
    db.flush()

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
            db.add(AgenteLineaAsignacion(agente_id=agente.id, linea_id=linea.id, es_activa=True))
        asignacion_resumen = {
            "modo": modo,
            "asignada": True,
            "linea_id": linea.id,
            "linea_numero": linea.numero,
        }

    if modo == "auto":
        linea = _choose_free_line_automatically(db, lada_objetivo)
        if linea:
            db.add(AgenteLineaAsignacion(agente_id=agente.id, linea_id=linea.id, es_activa=True))
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

    db.commit()
    db.refresh(agente)

    return {
        "status": "success",
        "data": {
            "agente_id": agente.id,
            "uuid": agente.uuid,
            "nombre": agente.nombre,
            "telefono": agente.telefono,
            "modo_asignacion": modo,
            "asignacion": asignacion_resumen,
            "lineas": _agent_active_lines(db, agente.id),
        },
    }


@router.get("/ladas")
async def listar_ladas(
    search: str | None = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Listar ladas para filtros de asignacion y alta manual."""
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
    codigo = _normalize_lada((payload or {}).get("codigo"))
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
    lada: str | None = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Listar lineas con estado ocupada/libre y agente asignado."""
    query = db.query(LineaTelefonica).filter(LineaTelefonica.es_activa.is_(True))
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
        resolved_lada = _extract_lada_from_number(linea.numero, known_codes)
        if lada and resolved_lada != _normalize_lada(lada):
            continue
        assign = assign_map.get(linea.id)
        ocupada = assign is not None
        if solo_ocupadas and not ocupada:
            continue
        data.append({
            "id": linea.id,
            "numero": linea.numero,
            "tipo": linea.tipo,
            "descripcion": linea.descripcion,
            "lada": resolved_lada,
            "ocupada": ocupada,
            "agente": {
                "id": assign.agente.id,
                "nombre": assign.agente.nombre,
                "telefono": assign.agente.telefono,
            } if assign and assign.agente else None,
            "fecha_asignacion": assign.fecha_asignacion.isoformat() if assign and assign.fecha_asignacion else None,
        })

    return {"status": "success", "data": data}


@router.post("/lineas")
async def crear_linea(
    payload: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Crear o reactivar una linea en inventario."""
    numero = _safe_line_number((payload or {}).get("numero", ""))
    tipo = str((payload or {}).get("tipo", "VOIP") or "VOIP").strip().upper()[:30] or "VOIP"
    descripcion = str((payload or {}).get("descripcion", "") or "").strip() or None

    existing = db.query(LineaTelefonica).filter(LineaTelefonica.numero == numero).first()
    if existing:
        existing.tipo = tipo
        existing.descripcion = descripcion
        existing.es_activa = True
        db.commit()
        db.refresh(existing)
        return {"status": "success", "data": {"id": existing.id, "numero": existing.numero, "tipo": existing.tipo, "reactivada": True}}

    row = LineaTelefonica(numero=numero, tipo=tipo, descripcion=descripcion, es_activa=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"status": "success", "data": {"id": row.id, "numero": row.numero, "tipo": row.tipo, "reactivada": False}}


@router.post("/lineas/{linea_id}/asignar")
async def asignar_linea_a_agente(
    linea_id: int,
    payload: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Asignar una linea a un agente y marcarla ocupada."""
    agente_id = int((payload or {}).get("agente_id") or 0)
    if agente_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debe enviar agente_id")

    linea = db.query(LineaTelefonica).filter(LineaTelefonica.id == linea_id, LineaTelefonica.es_activa.is_(True)).first()
    if not linea:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linea no encontrada")

    agente = db.query(DatoImportado).filter(DatoImportado.id == agente_id, DatoImportado.es_activo.is_(True)).first()
    if not agente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente no encontrado")

    current = db.query(AgenteLineaAsignacion).filter(
        AgenteLineaAsignacion.linea_id == linea_id,
        AgenteLineaAsignacion.es_activa.is_(True),
    ).first()
    if current and current.agente_id != agente_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La linea ya esta ocupada")
    if current and current.agente_id == agente_id:
        return {"status": "success", "message": "La linea ya estaba asignada a este agente"}

    row = AgenteLineaAsignacion(agente_id=agente_id, linea_id=linea_id, es_activa=True)
    db.add(row)
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
    agente_id = int((payload or {}).get("agente_id") or 0)

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
    current.fecha_liberacion = datetime.utcnow()
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
    linea = db.query(LineaTelefonica).filter(LineaTelefonica.id == linea_id, LineaTelefonica.es_activa.is_(True)).first()
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
    if not current_user.get("es_admin", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo admin puede modificar cuota")

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


@router.post("/backup")
async def generar_respaldo_manual(
    payload: dict | None = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generar respaldo semanal manual de la base de datos."""
    if not current_user.get("es_admin", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo admin puede generar respaldo")
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
    if not current_user.get("es_admin", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo admin puede consultar la configuración de respaldos")
    return {"status": "success", "data": get_backup_settings(db)}


@router.put("/backup/config")
async def actualizar_configuracion_respaldo(
    payload: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Guardar ruta persistente de respaldos."""
    if not current_user.get("es_admin", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo admin puede modificar la configuración de respaldos")
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
    if not current_user.get("es_admin", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo admin puede restaurar respaldos")
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
    """Obtener payload y URL pública del QR independiente de un agente."""
    agente = db.query(DatoImportado).filter(
        DatoImportado.id == agente_id,
        DatoImportado.es_activo.is_(True)
    ).first()
    if not agente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente no encontrado")

    public_base_url = config.get_public_base_url(request)
    public_url = f"{public_base_url}/api/qr/public/verify/{agente.uuid}"
    lineas_agente = _agent_active_lines(db, agente.id)
    payload = {
        "agente_id": agente.id,
        "uuid": agente.uuid,
        "nombre": agente.nombre,
        "telefono": agente.telefono,
        "numero_voip": _extract_voip(agente),
        "tiene_asignacion": _has_assignment(agente) or bool(lineas_agente),
        "lineas": lineas_agente,
        "public_url": public_url,
    }

    generator = QRGenerator()
    filename = f"agente_{agente.id}_{agente.uuid}.png"
    filepath = generator.generate_qr_from_text(public_url, filename)
    agente.qr_filename = filename
    agente.contenido_qr = json.dumps(payload, ensure_ascii=False)
    db.add(agente)
    db.commit()

    return {"status": "success", "data": {**payload, "qr_filename": filename, "qr_path": filepath}}


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


@router.get("/public/verify/{uuid}", response_class=HTMLResponse)
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
    pago = db.query(PagoSemanal).filter(
        PagoSemanal.agente_id == agente.id,
        PagoSemanal.semana_inicio == semana_ref
    ).first()

    payload = {
        "status": "success",
        "agente": {
            "id": agente.id,
            "uuid": agente.uuid,
            "nombre": agente.nombre,
            "telefono": agente.telefono,
            "tiene_asignacion": _has_assignment(agente),
        },
        "semana_inicio": semana_ref.isoformat(),
        "pagado": bool(pago.pagado) if pago else False,
        "monto": float(pago.monto) if pago else 0.0,
        "fecha_pago": pago.fecha_pago.isoformat() if pago and pago.fecha_pago else None,
    }
    return _render_public_status_page(payload)


@router.get("/public/verify-by-id/{agente_id}", response_class=HTMLResponse)
async def verificar_publico_por_id(
    agente_id: int,
    semana: date | None = Query(None),
    db: Session = Depends(get_db),
):
    """Verificacion publica para escaneo QR por ID de agente."""
    agente = db.query(DatoImportado).filter(
        DatoImportado.id == agente_id,
        DatoImportado.es_activo.is_(True)
    ).first()
    if not agente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente no encontrado")

    semana_ref = monday_of_week(semana or date.today())
    pago = db.query(PagoSemanal).filter(
        PagoSemanal.agente_id == agente.id,
        PagoSemanal.semana_inicio == semana_ref
    ).first()

    payload = {
        "status": "success",
        "agente": {
            "id": agente.id,
            "uuid": agente.uuid,
            "nombre": agente.nombre,
            "telefono": agente.telefono,
            "tiene_asignacion": _has_assignment(agente),
        },
        "semana_inicio": semana_ref.isoformat(),
        "pagado": bool(pago.pagado) if pago else False,
        "monto": float(pago.monto) if pago else 0.0,
        "fecha_pago": pago.fecha_pago.isoformat() if pago and pago.fecha_pago else None,
    }
    return _render_public_status_page(payload)
