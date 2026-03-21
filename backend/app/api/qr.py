"""Endpoints de verificacion QR para agentes y pagos semanales."""

from datetime import date, datetime, timedelta
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.orm import get_db
from app.models import DatoImportado, PagoSemanal
from app.schemas import PagoSemanalCrear, PagoSemanalRespuesta
from app.security import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/qr", tags=["QR Verificacion"])


def _monday_of_week(ref: date) -> date:
    """Return monday for a given date."""
    return ref - timedelta(days=ref.weekday())


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

    semana = _monday_of_week(pago_in.semana_inicio)
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
            monto=pago_in.monto,
            pagado=pago_in.pagado,
            fecha_pago=datetime.utcnow() if pago_in.pagado else None,
            observaciones=pago_in.observaciones,
        )
        db.add(pago)
    else:
        pago.telefono = pago_in.telefono
        pago.numero_voip = pago_in.numero_voip
        pago.monto = pago_in.monto
        pago.pagado = pago_in.pagado
        pago.observaciones = pago_in.observaciones
        pago.fecha_pago = datetime.utcnow() if pago_in.pagado else None

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

    semana_ref = _monday_of_week(semana or date.today())
    pago = db.query(PagoSemanal).filter(
        PagoSemanal.agente_id == agente_id,
        PagoSemanal.semana_inicio == semana_ref
    ).first()

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
        },
        "verificacion": {
            "telefono_valido": telefono_valido,
            "voip_valido": voip_valido,
            "asignacion_valida": telefono_valido and voip_valido,
            "semana_inicio": semana_ref.isoformat(),
            "pagado": bool(pago.pagado) if pago else False,
            "monto": float(pago.monto) if pago else 0.0,
            "fecha_pago": pago.fecha_pago.isoformat() if pago and pago.fecha_pago else None,
            "observaciones": pago.observaciones if pago else None,
        }
    }


@router.get("/public/verify/{uuid}")
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

    semana_ref = _monday_of_week(semana or date.today())
    pago = db.query(PagoSemanal).filter(
        PagoSemanal.agente_id == agente.id,
        PagoSemanal.semana_inicio == semana_ref
    ).first()

    return {
        "status": "success",
        "agente": {
            "uuid": agente.uuid,
            "nombre": agente.nombre,
            "telefono": agente.telefono,
        },
        "semana_inicio": semana_ref.isoformat(),
        "pagado": bool(pago.pagado) if pago else False,
        "monto": float(pago.monto) if pago else 0.0,
        "fecha_pago": pago.fecha_pago.isoformat() if pago and pago.fecha_pago else None,
    }


@router.get("/public/verify-by-id/{agente_id}")
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

    semana_ref = _monday_of_week(semana or date.today())
    pago = db.query(PagoSemanal).filter(
        PagoSemanal.agente_id == agente.id,
        PagoSemanal.semana_inicio == semana_ref
    ).first()

    return {
        "status": "success",
        "agente": {
            "id": agente.id,
            "uuid": agente.uuid,
            "nombre": agente.nombre,
            "telefono": agente.telefono,
        },
        "semana_inicio": semana_ref.isoformat(),
        "pagado": bool(pago.pagado) if pago else False,
        "monto": float(pago.monto) if pago else 0.0,
        "fecha_pago": pago.fecha_pago.isoformat() if pago and pago.fecha_pago else None,
    }
