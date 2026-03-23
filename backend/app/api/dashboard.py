"""Endpoints de dashboard operativo."""

from datetime import date, datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.orm import get_db
from app.models import (
    AgenteLineaAsignacion,
    AlertaPago,
    DatoImportado,
    ImportLog,
    LineaTelefonica,
    Usuario,
)
from app.security import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


def _normalize_day(raw_value) -> str | None:
    """Normalizar fechas devueltas por SQL a ISO date."""
    if raw_value is None:
        return None
    if isinstance(raw_value, datetime):
        return raw_value.date().isoformat()
    if isinstance(raw_value, date):
        return raw_value.isoformat()
    return str(raw_value)


def _build_activity_series(agent_rows: list[dict], import_rows: list[dict]) -> list[dict]:
    """Construir serie diaria de 7 dias combinando agentes e importaciones."""
    today = datetime.now(timezone.utc).date()
    days = [today - timedelta(days=offset) for offset in range(6, -1, -1)]

    agent_map = {
        _normalize_day(row.get("day")): {
            "registros": int(row.get("registros") or 0),
            "qr": int(row.get("qr") or 0),
        }
        for row in agent_rows
    }
    import_map = {
        _normalize_day(row.get("day")): {
            "importaciones": int(row.get("importaciones") or 0),
            "fallidas": int(row.get("fallidas") or 0),
        }
        for row in import_rows
    }

    series = []
    for item in days:
        key = item.isoformat()
        agent_info = agent_map.get(key, {})
        import_info = import_map.get(key, {})
        series.append(
            {
                "date": key,
                "label": item.strftime("%d/%m"),
                "registros": int(agent_info.get("registros") or 0),
                "qr": int(agent_info.get("qr") or 0),
                "importaciones": int(import_info.get("importaciones") or 0),
                "fallidas": int(import_info.get("fallidas") or 0),
            }
        )
    return series


def _fetch_agent_snapshot(db: Session) -> dict:
    """Obtener metricas reales de agentes priorizando la vista sincronizada."""
    candidates = [
        ("registro_agentes.datos_importados", "registro_agentes"),
        ("datos_importados", "database_manager"),
    ]
    since = datetime.now(timezone.utc) - timedelta(days=6)

    for table_ref, source_name in candidates:
        try:
            total = db.execute(text(f"SELECT COUNT(*) FROM {table_ref}")).scalar()
            active = db.execute(
                text(f"SELECT COUNT(*) FROM {table_ref} WHERE COALESCE(es_activo, 1) = 1")
            ).scalar()
            qr_total = db.execute(
                text(
                    f"""
                    SELECT COUNT(*)
                    FROM {table_ref}
                    WHERE qr_filename IS NOT NULL
                      AND qr_filename <> ''
                    """
                )
            ).scalar()
            qr_active = db.execute(
                text(
                    f"""
                    SELECT COUNT(*)
                    FROM {table_ref}
                    WHERE COALESCE(es_activo, 1) = 1
                      AND qr_filename IS NOT NULL
                      AND qr_filename <> ''
                    """
                )
            ).scalar()

            recent_rows = db.execute(
                text(
                    f"""
                    SELECT
                        id,
                        nombre,
                        fecha_creacion,
                        COALESCE(es_activo, 1) AS es_activo,
                        CASE WHEN qr_filename IS NOT NULL AND qr_filename <> '' THEN 1 ELSE 0 END AS has_qr
                    FROM {table_ref}
                                        ORDER BY COALESCE(fecha_creacion, fecha_modificacion) DESC, id DESC
                    LIMIT 5
                    """
                )
            ).mappings().all()

            activity_rows = db.execute(
                text(
                    f"""
                    SELECT
                        DATE(fecha_creacion) AS day,
                        COUNT(*) AS registros,
                        SUM(CASE WHEN qr_filename IS NOT NULL AND qr_filename <> '' THEN 1 ELSE 0 END) AS qr
                    FROM {table_ref}
                    WHERE fecha_creacion >= :since
                    GROUP BY DATE(fecha_creacion)
                    ORDER BY day ASC
                    """
                ),
                {"since": since},
            ).mappings().all()

            return {
                "source": source_name,
                "total": int(total or 0),
                "active": int(active or 0),
                "inactive": max(0, int(total or 0) - int(active or 0)),
                "qr_total": int(qr_total or 0),
                "qr_active": int(qr_active or 0),
                "recent_agents": [
                    {
                        "id": int(row.get("id") or 0),
                        "nombre": row.get("nombre") or f"Agente {row.get('id')}",
                        "fecha_creacion": row.get("fecha_creacion").isoformat() if row.get("fecha_creacion") else None,
                        "es_activo": bool(row.get("es_activo")),
                        "has_qr": bool(row.get("has_qr")),
                    }
                    for row in recent_rows
                ],
                "activity_rows": [dict(row) for row in activity_rows],
            }
        except Exception:
            continue

    recent_agents = db.query(DatoImportado).order_by(DatoImportado.fecha_creacion.desc()).limit(5).all()
    recent_agent_data = [
        {
            "id": item.id,
            "nombre": item.nombre or f"Agente {item.id}",
            "fecha_creacion": item.fecha_creacion.isoformat() if item.fecha_creacion else None,
            "es_activo": bool(item.es_activo),
            "has_qr": bool(item.qr_filename),
        }
        for item in recent_agents
    ]
    since_naive = since.replace(tzinfo=None)
    recent_items = db.query(DatoImportado).filter(DatoImportado.fecha_creacion >= since_naive).all()
    activity_map: dict[str, dict[str, int]] = {}
    for item in recent_items:
        if not item.fecha_creacion:
            continue
        key = item.fecha_creacion.date().isoformat()
        bucket = activity_map.setdefault(key, {"day": key, "registros": 0, "qr": 0})
        bucket["registros"] += 1
        if item.qr_filename:
            bucket["qr"] += 1

    total = db.query(DatoImportado).count()
    active = db.query(DatoImportado).filter(DatoImportado.es_activo.is_(True)).count()
    qr_total = db.query(DatoImportado).filter(
        DatoImportado.qr_filename.isnot(None),
        DatoImportado.qr_filename != "",
    ).count()
    qr_active = db.query(DatoImportado).filter(
        DatoImportado.es_activo.is_(True),
        DatoImportado.qr_filename.isnot(None),
        DatoImportado.qr_filename != "",
    ).count()
    return {
        "source": "database_manager",
        "total": int(total or 0),
        "active": int(active or 0),
        "inactive": max(0, int(total or 0) - int(active or 0)),
        "qr_total": int(qr_total or 0),
        "qr_active": int(qr_active or 0),
        "recent_agents": recent_agent_data,
        "activity_rows": list(activity_map.values()),
    }


def _build_operational_alerts(
    total_registros: int,
    total_activos: int,
    qr_pendientes: int,
    importaciones_fallidas: int,
    alertas_pago_pendientes: int,
    lineas_activas: int,
    lineas_asignadas_activas: int,
    sin_linea: int = 0,
) -> list[dict]:
    """Armar alertas accionables para el dashboard."""
    alerts: list[dict] = []

    if total_registros == 0:
        alerts.append(
            {
                "level": "info",
                "title": "Sin agentes cargados",
                "detail": "Aun no hay registros persistidos en datos_importados.",
                "action_section": "importar",
            }
        )
    elif total_activos == 0:
        alerts.append(
            {
                "level": "danger",
                "title": "Todos los agentes estan inactivos",
                "detail": "Hay historico en BD, pero no existen agentes activos para la operacion actual.",
                "action_section": "cambiosBajas",
            }
        )

    if sin_linea > 0:
        alerts.append(
            {
                "level": "warning",
                "title": "Agentes pendiente de asignación de línea",
                "detail": f"Hay {sin_linea} agente(s) activos sin número de línea. Asigna líneas desde 'Estado de Agentes'.",
                "action_section": "estadoAgentes",
            }
        )

    if qr_pendientes > 0:
        alerts.append(
            {
                "level": "warning",
                "title": "QR pendientes",
                "detail": f"Hay {qr_pendientes} registros sin QR generado.",
                "action_section": "qr",
            }
        )

    if importaciones_fallidas > 0:
        alerts.append(
            {
                "level": "warning",
                "title": "Importaciones fallidas",
                "detail": f"Se registraron {importaciones_fallidas} importaciones con error.",
                "action_section": "importar",
            }
        )

    if alertas_pago_pendientes > 0:
        alerts.append(
            {
                "level": "warning",
                "title": "Alertas de pago pendientes",
                "detail": f"Hay {alertas_pago_pendientes} alertas sin atender.",
                "action_section": "qr",
            }
        )

    if lineas_activas > 0 and lineas_asignadas_activas >= lineas_activas:
        alerts.append(
            {
                "level": "info",
                "title": "Sin lineas disponibles",
                "detail": "Todas las lineas activas ya estan asignadas a agentes.",
                "action_section": "altasAgentes",
            }
        )

    return alerts[:6]


@router.get("/summary")
async def dashboard_summary(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Resumen operativo para dashboard principal."""
    now = datetime.now(timezone.utc)
    online_window = now - timedelta(minutes=30)
    week_start = (now - timedelta(days=now.weekday())).date()

    agent_snapshot = _fetch_agent_snapshot(db)
    total_registros = int(agent_snapshot["total"])
    total_activos = int(agent_snapshot["active"])
    total_inactivos = int(agent_snapshot["inactive"])
    total_qr = int(agent_snapshot["qr_total"])
    total_qr_activos = int(agent_snapshot["qr_active"])
    total_qr_pendientes = max(0, total_registros - total_qr)
    source_db = agent_snapshot["source"]

    total_importaciones = db.query(ImportLog).count()
    importaciones_exitosas = db.query(ImportLog).filter(ImportLog.estado == "SUCCESS").count()
    importaciones_fallidas = db.query(ImportLog).filter(ImportLog.estado == "FAILED").count()

    usuarios_activos = db.query(Usuario).filter(Usuario.es_activo.is_(True)).count()
    usuarios_online = db.query(Usuario).filter(
        Usuario.es_activo.is_(True),
        Usuario.fecha_ultima_sesion.isnot(None),
        Usuario.fecha_ultima_sesion >= online_window,
    ).count()

    lineas_activas = db.query(LineaTelefonica).filter(LineaTelefonica.es_activa.is_(True)).count()
    lineas_asignadas_activas = db.query(AgenteLineaAsignacion).filter(
        AgenteLineaAsignacion.es_activa.is_(True)
    ).count()
    alertas_pago_pendientes = db.query(AlertaPago).filter(AlertaPago.atendida.is_(False)).count()

    # Agentes activos sin línea telefónica asignada
    sin_linea_count = db.execute(
        text(
            """
            SELECT COUNT(*)
            FROM datos_importados d
            LEFT JOIN agente_linea_asignaciones ala
                ON ala.agente_id = d.id AND ala.es_activa = 1
            WHERE COALESCE(d.es_activo, 1) = 1
              AND ala.id IS NULL
            """
        )
    ).scalar()

    online_users = db.query(Usuario).filter(
        Usuario.es_activo.is_(True),
        Usuario.fecha_ultima_sesion.isnot(None),
    ).order_by(Usuario.fecha_ultima_sesion.desc()).limit(8).all()

    online_users_data = []
    for u in online_users:
        last_session = u.fecha_ultima_sesion
        if last_session and last_session.tzinfo is None:
            last_session = last_session.replace(tzinfo=timezone.utc)
        seconds_ago = max(0, int((now - last_session).total_seconds())) if last_session else None
        online_users_data.append(
            {
                "id": u.id,
                "username": u.username,
                "nombre_completo": u.nombre_completo,
                "es_admin": bool(u.es_admin),
                "fecha_ultima_sesion": u.fecha_ultima_sesion.isoformat() if u.fecha_ultima_sesion else None,
                "seconds_since_last_session": seconds_ago,
                "is_online": bool(last_session and last_session >= online_window),
            }
        )

    recent_imports = db.query(ImportLog).order_by(ImportLog.fecha_inicio.desc()).limit(5).all()
    recent_imports_data = [
        {
            "id": imp.id,
            "archivo_nombre": imp.archivo_nombre,
            "tabla_destino": imp.tabla_destino,
            "estado": imp.estado,
            "registros_importados": imp.registros_importados,
            "registros_fallidos": imp.registros_fallidos,
            "fecha_inicio": imp.fecha_inicio.isoformat() if imp.fecha_inicio else None,
        }
        for imp in recent_imports
    ]

    import_activity_rows = db.execute(
        text(
            """
            SELECT
                DATE(fecha_inicio) AS day,
                COUNT(*) AS importaciones,
                SUM(CASE WHEN estado = 'FAILED' THEN 1 ELSE 0 END) AS fallidas
            FROM import_logs
            WHERE fecha_inicio >= :since
            GROUP BY DATE(fecha_inicio)
            ORDER BY day ASC
            """
        ),
        {"since": now - timedelta(days=6)},
    ).mappings().all()

    pagos_pendientes_semana = db.execute(
        text(
            """
            SELECT COUNT(*)
            FROM pagos_semanales
            WHERE semana_inicio = :week_start
              AND COALESCE(pagado, 0) = 0
            """
        ),
        {"week_start": week_start},
    ).scalar()

    activity_series = _build_activity_series(
        agent_snapshot.get("activity_rows", []),
        [dict(row) for row in import_activity_rows],
    )
    alerts = _build_operational_alerts(
        total_registros=total_registros,
        total_activos=total_activos,
        qr_pendientes=total_qr_pendientes,
        importaciones_fallidas=importaciones_fallidas,
        alertas_pago_pendientes=int(alertas_pago_pendientes or 0),
        lineas_activas=int(lineas_activas or 0),
        lineas_asignadas_activas=int(lineas_asignadas_activas or 0),
        sin_linea=int(sin_linea_count or 0),
    )

    # Metadatos de esquema para apoyar visualización operativa.
    # En producción (MariaDB) se usa information_schema. Para tests SQLite,
    # se usa sqlite_master para evitar errores por funciones no soportadas.
    dialect = getattr(getattr(db, "bind", None), "dialect", None)
    dialect_name = getattr(dialect, "name", "")
    if dialect_name == "sqlite":
        db_name = "sqlite"
        table_count = db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                """
            )
        ).scalar()
        view_count = db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM sqlite_master
                WHERE type = 'view'
                """
            )
        ).scalar()
    else:
        db_name = db.execute(text("SELECT DATABASE()")).scalar()
        table_count = db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE'
                """
            )
        ).scalar()
        view_count = db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = DATABASE() AND table_type = 'VIEW'
                """
            )
        ).scalar()

    return {
        "status": "success",
        "generated_at": now.isoformat(),
        "database": {
            "name": db_name,
            "agent_source": source_db,
            "tables": int(table_count or 0),
            "views": int(view_count or 0),
        },
        "totals": {
            "registros": total_registros,
            "registros_activos": total_activos,
            "registros_inactivos": total_inactivos,
            "importaciones": total_importaciones,
            "importaciones_exitosas": importaciones_exitosas,
            "importaciones_fallidas": importaciones_fallidas,
            "qr_generados": total_qr,
            "qr_activos": total_qr_activos,
            "qr_pendientes": total_qr_pendientes,
            "usuarios": usuarios_activos,
            "usuarios_online": usuarios_online,
            "lineas_activas": int(lineas_activas or 0),
            "lineas_asignadas_activas": int(lineas_asignadas_activas or 0),
            "alertas_pago_pendientes": int(alertas_pago_pendientes or 0),
            "pagos_pendientes_semana": int(pagos_pendientes_semana or 0),
            "sin_linea": int(sin_linea_count or 0),
        },
        "online_window_minutes": 30,
        "alerts": alerts,
        "online_users": online_users_data,
        "recent_imports": recent_imports_data,
        "recent_agents": agent_snapshot.get("recent_agents", []),
        "activity_7_days": activity_series,
    }
