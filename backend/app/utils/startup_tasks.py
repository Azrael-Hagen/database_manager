"""Tareas automáticas ejecutadas en el inicio del servidor."""

import json
import logging

from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from app.models import DatoImportado
from app.qr import QRGenerator
from app.config import config
from app.utils.agent_cleanup import cleanup_redundant_agents

logger = logging.getLogger(__name__)


def auto_qr_al_inicio(db: Session) -> dict:
    """
    Genera QR (tipo UUID-fallback) para todos los agentes activos que no tienen uno.
    Se ejecuta en el arranque del servidor como tarea no bloqueante.
    """
    try:
        agentes_sin_qr = (
            db.query(DatoImportado)
            .filter(
                DatoImportado.es_activo.is_(True),
                or_(
                    DatoImportado.qr_filename.is_(None),
                    DatoImportado.qr_filename == "",
                ),
            )
            .all()
        )
    except Exception as exc:
        logger.warning("No se pudo consultar agentes sin QR en inicio: %s", exc)
        return {"status": "skipped", "reason": str(exc)}

    if not agentes_sin_qr:
        logger.info("Inicio: todos los agentes activos ya tienen QR generado.")
        return {"status": "ok", "totales_sin_qr": 0, "generados": 0, "errores": 0}

    public_base_url = config.get_public_base_url()
    generados = 0
    errores = 0

    for agente in agentes_sin_qr:
        try:
            public_url = f"{public_base_url}/api/qr/public/verify/{agente.uuid}"
            generator = QRGenerator()
            filename = f"agente_{agente.id}_sin_linea_{agente.uuid}.png"
            generator.generate_qr_from_text(public_url, filename)
            payload = {
                "agente_id": agente.id,
                "uuid": agente.uuid,
                "public_url": public_url,
                "qr_mode": "startup_uuid",
                "es_qr_seguro": False,
            }
            agente.qr_filename = filename
            agente.contenido_qr = json.dumps(payload, ensure_ascii=False)
            generados += 1
        except Exception as exc:
            logger.warning(
                "No se pudo generar QR para agente %s en inicio: %s", agente.id, exc
            )
            errores += 1

    if generados > 0:
        try:
            db.commit()
            logger.info(
                "Inicio: QR auto-generados=%s errores=%s (total sin QR=%s)",
                generados,
                errores,
                len(agentes_sin_qr),
            )
        except Exception as exc:
            logger.error("Error al guardar QRs generados en inicio: %s", exc)
            db.rollback()
            return {
                "status": "error",
                "generados": 0,
                "errores": errores + generados,
                "reason": str(exc),
            }

    return {
        "status": "ok",
        "totales_sin_qr": len(agentes_sin_qr),
        "generados": generados,
        "errores": errores,
    }


def reporte_sin_linea_inicio(db: Session) -> dict:
    """
    Cuenta agentes activos sin línea para log diagnóstico.
    No bloquea el inicio si falla.
    """
    try:
        count = db.execute(
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
        sin_linea = int(count or 0)
        if sin_linea > 0:
            logger.warning(
                "Inicio: hay %s agente(s) activos sin línea asignada. "
                "Ir a sección 'Sin Línea' para gestionar.",
                sin_linea,
            )
        else:
            logger.info("Inicio: todos los agentes activos tienen línea asignada.")
        return {"sin_linea": sin_linea}
    except Exception as exc:
        logger.warning("No se pudo calcular agentes sin linea en inicio: %s", exc)
        return {"sin_linea": -1}


def depuracion_agentes_inicio(db: Session) -> dict:
    """Depura agentes redundantes/de prueba al inicio si está habilitado por configuración."""
    if not bool(getattr(config, "AUTO_AGENT_DATA_CLEANUP_ON_STARTUP", False)):
        return {"status": "skipped", "reason": "disabled_by_config"}

    try:
        result = cleanup_redundant_agents(db, apply_changes=True, sync_legacy=True)
        db.commit()
        logger.info(
            "Inicio: depuracion agentes aplicada=%s eliminados=%s test=%s duplicados=%s",
            result.get("applied"),
            result.get("deleted"),
            result.get("test_like_candidates"),
            result.get("duplicate_candidates"),
        )
        return {"status": "ok", **result}
    except Exception as exc:
        db.rollback()
        logger.warning("No se pudo depurar agentes redundantes en inicio: %s", exc)
        return {"status": "error", "reason": str(exc)}
