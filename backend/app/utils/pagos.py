"""Utilidades de cobro semanal y alertas de pago."""

from datetime import date, datetime, timedelta
from typing import Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import AgenteLineaAsignacion, AlertaPago, ConfigSistema, DatoImportado, PagoSemanal

CUOTA_SEMANAL_KEY = "CUOTA_SEMANAL"
LAST_ALERT_CHECK_KEY = "LAST_ALERT_CHECK_DATE"
DEFAULT_CUOTA = 300.0
MANUAL_DEUDA_AJUSTE_PREFIX = "DEUDA_AJUSTE_MANUAL_AGENTE_"


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


def _manual_deuda_key(agente_id: int) -> str:
    return f"{MANUAL_DEUDA_AJUSTE_PREFIX}{int(agente_id)}"


def get_manual_deuda_ajuste(db: Session, agente_id: int) -> float:
    row = _get_config_row(db, _manual_deuda_key(agente_id))
    if not row or row.valor in (None, ""):
        return 0.0
    try:
        return float(row.valor)
    except (TypeError, ValueError):
        return 0.0


def set_manual_deuda_ajuste(db: Session, agente_id: int, monto: float) -> float:
    value = float(monto)
    set_config_value(db, _manual_deuda_key(agente_id), f"{value:.2f}")
    return value


def _weeks_between(start_monday: date, end_monday: date) -> int:
    if end_monday < start_monday:
        return 0
    return ((end_monday - start_monday).days // 7) + 1


def _agent_start_week(db: Session, agente: DatoImportado, semana_ref: date) -> date:
    pago_min = db.query(PagoSemanal).filter(PagoSemanal.agente_id == agente.id).order_by(PagoSemanal.semana_inicio.asc()).first()
    if pago_min and pago_min.semana_inicio:
        return monday_of_week(pago_min.semana_inicio)
    created = agente.fecha_creacion.date() if agente.fecha_creacion else semana_ref
    return monday_of_week(created)


def _active_billable_assignments(db: Session, agente_id: int, semana_ref: date) -> list[dict]:
    rows = db.query(AgenteLineaAsignacion).filter(
        AgenteLineaAsignacion.agente_id == agente_id,
        AgenteLineaAsignacion.es_activa.is_(True),
    ).all()

    items: list[dict] = []
    for row in rows:
        if not row.linea or not row.linea.es_activa:
            continue
        raw_start = row.cobro_desde_semana
        if raw_start is None and row.fecha_asignacion:
            raw_start = row.fecha_asignacion.date()
        start_week = monday_of_week(raw_start or semana_ref)
        if start_week > semana_ref:
            continue
        items.append(
            {
                "linea_id": int(row.linea_id),
                "start_week": start_week,
                "cargo_inicial": float(row.cargo_inicial or 0),
            }
        )
    return items


def resumen_cobranza_agente(db: Session, agente: DatoImportado, semana: date | None = None) -> dict:
    """Resumen de deuda acumulada y estado semanal de un agente."""
    semana_ref = monday_of_week(semana or date.today())
    tarifa_por_linea = float(get_cuota_semanal(db))
    assignments = _active_billable_assignments(db, agente.id, semana_ref)
    lineas_activas = len(assignments)

    cuota_semanal_total = float(tarifa_por_linea) * float(lineas_activas)
    deuda_base_total = 0.0
    for item in assignments:
        weeks_due = _weeks_between(item["start_week"], semana_ref)
        deuda_base_total += float(tarifa_por_linea) * float(weeks_due)
        deuda_base_total += float(item["cargo_inicial"])

    ajuste_manual_deuda = float(get_manual_deuda_ajuste(db, agente.id))
    deuda_total = max(deuda_base_total + ajuste_manual_deuda, 0.0)

    total_abonado_rows = db.query(PagoSemanal.monto).filter(
        PagoSemanal.agente_id == agente.id,
        PagoSemanal.semana_inicio <= semana_ref,
    ).all()
    total_abonado = float(sum(float(r[0] or 0) for r in total_abonado_rows))

    saldo_acumulado = max(deuda_total - total_abonado, 0.0)

    pago_semana = db.query(PagoSemanal).filter(
        PagoSemanal.agente_id == agente.id,
        PagoSemanal.semana_inicio == semana_ref,
    ).first()
    abonado_semana = float(pago_semana.monto or 0) if pago_semana else 0.0
    pagado_semana = bool(pago_semana.pagado) if pago_semana else False
    saldo_semana = max(float(cuota_semanal_total) - abonado_semana, 0.0)

    if tarifa_por_linea <= 0:
        semanas_pendientes = 0
    else:
        semanas_pendientes = int(saldo_acumulado // float(tarifa_por_linea))
        if saldo_acumulado % float(tarifa_por_linea) > 0.0001:
            semanas_pendientes += 1

    if lineas_activas == 0 and saldo_acumulado <= 0.0001:
        pagado_semana = True

    return {
        "semana_inicio": semana_ref,
        "tarifa_linea_semanal": float(tarifa_por_linea),
        "lineas_activas": int(lineas_activas),
        "cuota_semanal": float(cuota_semanal_total),
        "deuda_base_total": float(deuda_base_total),
        "ajuste_manual_deuda": float(ajuste_manual_deuda),
        "deuda_total": float(deuda_total),
        "total_abonado": float(total_abonado),
        "saldo_acumulado": float(saldo_acumulado),
        "semanas_pendientes": max(0, semanas_pendientes),
        "abonado_semana": float(abonado_semana),
        "saldo_semana": float(saldo_semana),
        "pagado_semana": bool(pagado_semana),
    }


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
            resumen = resumen_cobranza_agente(db, agente, semana)
            if int(resumen.get("lineas_activas") or 0) == 0:
                continue
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
    tarifa_linea = get_cuota_semanal(db)

    query = db.query(DatoImportado).filter(DatoImportado.es_activo.is_(True))
    if agente_buscar:
        query = query.filter(DatoImportado.nombre.ilike(f"%{agente_buscar}%"))
    if empresa_buscar:
        query = query.filter(DatoImportado.empresa.ilike(f"%{empresa_buscar}%"))

    agentes = query.all()

    filas = []
    total_pagados = 0
    total_pendientes = 0
    deuda_total_global = 0.0
    total_abonado_global = 0.0
    saldo_global = 0.0
    monto_semana_reportado = 0.0
    cuota_esperada_global = 0.0

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
        resumen = resumen_cobranza_agente(db, agente, semana_ref)
        cuota_agente = float(resumen.get("cuota_semanal") or 0)
        saldo = max(cuota_agente - monto_pagado, 0.0)

        if float(resumen.get("saldo_acumulado") or 0) <= 0.0001:
            pagado = True

        if pagado:
            total_pagados += 1
        else:
            total_pendientes += 1

        deuda_total_global += float(resumen.get("deuda_total") or 0)
        total_abonado_global += float(resumen.get("total_abonado") or 0)
        saldo_global += float(resumen.get("saldo_acumulado") or 0)
        monto_semana_reportado += monto_pagado
        cuota_esperada_global += cuota_agente

        filas.append({
            "pago_id": pago.id if pago else None,
            "agente_id": agente.id,
            "uuid": agente.uuid,
            "nombre": agente.nombre,
            "telefono": agente.telefono,
            "empresa": agente.empresa,
            "pagado": pagado,
            "monto_pagado": monto_pagado,
            "cuota": cuota_agente,
            "lineas_activas": int(resumen.get("lineas_activas") or 0),
            "tarifa_linea_semanal": float(resumen.get("tarifa_linea_semanal") or tarifa_linea),
            "saldo": saldo,
            "deuda_total": resumen["deuda_total"],
            "total_abonado": resumen["total_abonado"],
            "saldo_acumulado": resumen["saldo_acumulado"],
            "semanas_pendientes": resumen["semanas_pendientes"],
            "fecha_pago": pago.fecha_pago.isoformat() if pago and pago.fecha_pago else None,
            "alerta_emitida": bool(alerta),
            "alerta_atendida": bool(alerta.atendida) if alerta else False,
        })

    filas.sort(key=lambda x: (x["pagado"], x["nombre"] or ""))

    monto_semana_ledger = float(
        db.query(func.coalesce(func.sum(PagoSemanal.monto), 0.0))
        .join(DatoImportado, DatoImportado.id == PagoSemanal.agente_id)
        .filter(
            PagoSemanal.semana_inicio == semana_ref,
            PagoSemanal.pagado.is_(True),
            DatoImportado.es_activo.is_(True),
        )
        .scalar()
        or 0.0
    )

    agentes_con_pagos_duplicados = (
        db.query(PagoSemanal.agente_id)
        .join(DatoImportado, DatoImportado.id == PagoSemanal.agente_id)
        .filter(
            PagoSemanal.semana_inicio == semana_ref,
            DatoImportado.es_activo.is_(True),
        )
        .group_by(PagoSemanal.agente_id)
        .having(func.count(PagoSemanal.id) > 1)
        .count()
    )

    deuda_total_global = round(deuda_total_global, 2)
    total_abonado_global = round(total_abonado_global, 2)
    saldo_global = round(saldo_global, 2)
    monto_semana_reportado = round(monto_semana_reportado, 2)
    monto_semana_ledger = round(monto_semana_ledger, 2)
    cuota_esperada_global = round(cuota_esperada_global, 2)

    discrepancia_semana = round(monto_semana_ledger - monto_semana_reportado, 2)
    discrepancia_saldo = round((deuda_total_global - total_abonado_global) - saldo_global, 2)

    discrepancias: list[dict] = []
    if agentes_con_pagos_duplicados > 0:
        discrepancias.append(
            {
                "codigo": "PAGOS_DUPLICADOS_AGENTE_SEMANA",
                "severidad": "media",
                "mensaje": "Existen agentes con mas de un pago registrado en la misma semana operativa.",
                "total_agentes": int(agentes_con_pagos_duplicados),
            }
        )
    if abs(discrepancia_semana) > 0.009:
        discrepancias.append(
            {
                "codigo": "DIFERENCIA_REPORTE_VS_LEDGER",
                "severidad": "alta",
                "mensaje": "El total semanal mostrado por agente no coincide con el total de pagos del ledger.",
                "monto_diferencia": discrepancia_semana,
            }
        )
    if abs(discrepancia_saldo) > 0.009:
        discrepancias.append(
            {
                "codigo": "DIFERENCIA_SALDO_GLOBAL",
                "severidad": "alta",
                "mensaje": "La formula deuda_total - total_abonado no coincide con el saldo acumulado global.",
                "monto_diferencia": discrepancia_saldo,
            }
        )

    return {
        "semana_inicio": semana_ref.isoformat(),
        "cuota_semanal": tarifa_linea,
        "filtros": {
            "agente": agente_buscar or "",
            "empresa": empresa_buscar or "",
        },
        "totales": {
            "agentes": len(filas),
            "pagados": total_pagados,
            "pendientes": total_pendientes,
            "cuota_esperada_global": cuota_esperada_global,
            "deuda_total_global": deuda_total_global,
            "total_abonado_global": total_abonado_global,
            "saldo_global": saldo_global,
            "monto_semana_reportado": monto_semana_reportado,
            "monto_semana_ledger": monto_semana_ledger,
            "discrepancia_semana": discrepancia_semana,
            "discrepancia_saldo": discrepancia_saldo,
        },
        "discrepancias": discrepancias,
        "data": filas,
    }
