"""Utilidades de cobro semanal y alertas de pago."""

from datetime import date, datetime, timedelta
from typing import Iterable

from sqlalchemy.orm import Session

from app.models import AlertaPago, ConfigSistema, DatoImportado, PagoSemanal

CUOTA_SEMANAL_KEY = "CUOTA_SEMANAL"
LAST_ALERT_CHECK_KEY = "LAST_ALERT_CHECK_DATE"
DEFAULT_CUOTA = 300.0


def monday_of_week(ref: date) -> date:
    """Return monday for a given date."""
    return ref - timedelta(days=ref.weekday())


def _iterate_days(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _get_config_row(db: Session, key: str) -> ConfigSistema | None:
    return db.query(ConfigSistema).filter(ConfigSistema.clave == key).first()


def get_config_value(db: Session, key: str, default: str) -> str:
    row = _get_config_row(db, key)
    if row is None:
        row = ConfigSistema(clave=key, valor=str(default))
        db.add(row)
        db.commit()
        db.refresh(row)
    return row.valor


def set_config_value(db: Session, key: str, value: str) -> str:
    row = _get_config_row(db, key)
    if row is None:
        row = ConfigSistema(clave=key, valor=str(value))
        db.add(row)
    else:
        row.valor = str(value)
    db.commit()
    return str(value)


def get_cuota_semanal(db: Session) -> float:
    value = get_config_value(db, CUOTA_SEMANAL_KEY, str(DEFAULT_CUOTA))
    try:
        return float(value)
    except (TypeError, ValueError):
        set_config_value(db, CUOTA_SEMANAL_KEY, str(DEFAULT_CUOTA))
        return DEFAULT_CUOTA


def set_cuota_semanal(db: Session, cuota: float) -> float:
    set_config_value(db, CUOTA_SEMANAL_KEY, f"{float(cuota):.2f}")
    return float(cuota)


def generar_alertas_miercoles_pendientes(db: Session, today: date | None = None) -> dict:
    """Generate unpaid alerts for each Wednesday since the last check."""
    today = today or date.today()

    first_default = (monday_of_week(today) - timedelta(days=1)).isoformat()
    last_check_raw = get_config_value(db, LAST_ALERT_CHECK_KEY, first_default)
    try:
        last_check = date.fromisoformat(last_check_raw)
    except ValueError:
        last_check = today

    # Check from next day to avoid duplicating the same run date.
    start_day = last_check + timedelta(days=1)

    alertas_creadas = 0
    semanas_revisadas = set()

    if start_day <= today:
        miercoles = [d for d in _iterate_days(start_day, today) if d.weekday() == 2]
    else:
        miercoles = []

    agentes = db.query(DatoImportado).filter(DatoImportado.es_activo.is_(True)).all()

    for dia in miercoles:
        semana = monday_of_week(dia)
        semanas_revisadas.add(semana.isoformat())

        for agente in agentes:
            pago = db.query(PagoSemanal).filter(
                PagoSemanal.agente_id == agente.id,
                PagoSemanal.semana_inicio == semana,
                PagoSemanal.pagado.is_(True)
            ).first()
            if pago:
                continue

            existe_alerta = db.query(AlertaPago).filter(
                AlertaPago.agente_id == agente.id,
                AlertaPago.semana_inicio == semana
            ).first()
            if existe_alerta:
                continue

            alerta = AlertaPago(
                agente_id=agente.id,
                semana_inicio=semana,
                motivo="Pago semanal pendiente (alerta de miercoles)",
                atendida=False,
            )
            db.add(alerta)
            alertas_creadas += 1

    set_config_value(db, LAST_ALERT_CHECK_KEY, today.isoformat())
    db.commit()

    return {
        "fecha_corte": today.isoformat(),
        "semanas_revisadas": sorted(semanas_revisadas),
        "alertas_creadas": alertas_creadas,
    }


def obtener_reporte_semanal(
    db: Session,
    semana: date | None = None,
    agente_buscar: str | None = None,
    empresa_buscar: str | None = None,
) -> dict:
    """Build weekly payment report per active agent."""
    semana_ref = monday_of_week(semana or date.today())
    cuota = get_cuota_semanal(db)

    query = db.query(DatoImportado).filter(DatoImportado.es_activo.is_(True))
    if agente_buscar:
        query = query.filter(DatoImportado.nombre.ilike(f"%{agente_buscar}%"))
    if empresa_buscar:
        query = query.filter(DatoImportado.empresa.ilike(f"%{empresa_buscar}%"))

    agentes = query.all()

    filas = []
    total_pagados = 0
    total_pendientes = 0

    for agente in agentes:
        pago = db.query(PagoSemanal).filter(
            PagoSemanal.agente_id == agente.id,
            PagoSemanal.semana_inicio == semana_ref
        ).first()

        alerta = db.query(AlertaPago).filter(
            AlertaPago.agente_id == agente.id,
            AlertaPago.semana_inicio == semana_ref
        ).first()

        pagado = bool(pago.pagado) if pago else False
        monto_pagado = float(pago.monto) if pago else 0.0
        saldo = max(cuota - monto_pagado, 0.0)

        if pagado:
            total_pagados += 1
        else:
            total_pendientes += 1

        filas.append({
            "agente_id": agente.id,
            "uuid": agente.uuid,
            "nombre": agente.nombre,
            "telefono": agente.telefono,
            "empresa": agente.empresa,
            "pagado": pagado,
            "monto_pagado": monto_pagado,
            "cuota": cuota,
            "saldo": saldo,
            "fecha_pago": pago.fecha_pago.isoformat() if pago and pago.fecha_pago else None,
            "alerta_emitida": bool(alerta),
            "alerta_atendida": bool(alerta.atendida) if alerta else False,
        })

    filas.sort(key=lambda x: (x["pagado"], x["nombre"] or ""))

    return {
        "semana_inicio": semana_ref.isoformat(),
        "cuota_semanal": cuota,
        "filtros": {
            "agente": agente_buscar or "",
            "empresa": empresa_buscar or "",
        },
        "totales": {
            "agentes": len(filas),
            "pagados": total_pagados,
            "pendientes": total_pendientes,
        },
        "data": filas,
    }
