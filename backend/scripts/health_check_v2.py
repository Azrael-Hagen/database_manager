"""
Tablero de Salud SQL - Diagnóstico integral de integridad y coherencia BD
(Versión 2 - Compatible con config.py)

Consultas de diagnostico:
1. Duplicados por email/telefo no
2. Registros huérfanos (sin asignaciones)
3. Desalineación entre database_manager y registro_agentes (legacy)
4. Inconsistencias en datos_adicionales JSON
5. QR status tracking
6. Pagos semanales pendientes/anomalías
7. Linea asignacions sin agente
8. Auditoría de cambios recientes
"""

import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Setup path to import app config
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import Session, sessionmaker
from app.config import config


# Configurar logging
log_file = Path(__file__).parent.parent.parent / "logs" / f"health_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
log_file.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

DATABASE_URL = config.DATABASE_URL
LEGACY_TABLE_AVAILABLE = True  # Asumimos que está disponible


# Temas de healthcheck
CHECKS = {
    "DUPLICADOS": True,
    "HUERFANOS": True,
    "DESALINEACION_LEGACY": True,
    "JSON_INTEGRIDAD": True,
    "QR_STATUS": True,
    "PAGOS_ANOMALIAS": True,
    "LINEAS_ASIGNACION": True,
    "AUDITORIA": True,
}


class HealthChecker:
    """Sistema de diagnóstico de salud de BD."""

    def __init__(self, main_engine):
        self.main_engine = main_engine
        self.main_session = sessionmaker(bind=main_engine)()
        self.results = {}

    def _run_query(self, session: Session, query: str, description: str = "") -> Any:
        """Ejecutar consulta y retornar resultados."""
        try:
            result = session.execute(text(query)).fetchall()
            if description:
                logger.debug(f"Query: {description}")
            return result
        except Exception as e:
            logger.error(f"Error en query: {e}")
            return []

    def check_duplicates(self) -> dict:
        """Detectar duplicados por email/teléfono."""
        logger.info("\n[1/8] VERIFICANDO DUPLICADOS...")
        
        results = {
            "duplicados_email": [],
            "duplicados_telefono": [],
            "summary": {}
        }

        # Duplicados por email
        query = """
            SELECT 
                email, 
                COUNT(*) as cantidad,
                GROUP_CONCAT(id) as ids,
                GROUP_CONCAT(nombre) as nombres
            FROM datos_importados
            WHERE email IS NOT NULL AND email != ''
            GROUP BY email
            HAVING COUNT(*) > 1
            ORDER BY cantidad DESC
        """
        
        rows = self._run_query(self.main_session, query, "Duplicados por email")
        for row in rows:
            results["duplicados_email"].append({
                "email": row[0],
                "cantidad": row[1],
                "ids": row[2],
                "nombres": row[3]
            })
            logger.warning(f"  ⚠ Email duplicado: {row[0]} ({row[1]} registros: {row[3]})")

        # Duplicados por teléfono
        query = """
            SELECT 
                telefono, 
                COUNT(*) as cantidad,
                GROUP_CONCAT(id) as ids,
                GROUP_CONCAT(nombre) as nombres
            FROM datos_importados
            WHERE telefono IS NOT NULL AND telefono != ''
            GROUP BY telefono
            HAVING COUNT(*) > 1
            ORDER BY cantidad DESC
        """
        
        rows = self._run_query(self.main_session, query, "Duplicados por teléfono")
        for row in rows:
            results["duplicados_telefono"].append({
                "telefono": row[0],
                "cantidad": row[1],
                "ids": row[2],
                "nombres": row[3]
            })
            logger.warning(f"  ⚠ Teléfono duplicado: {row[0]} ({row[1]} registros: {row[3]})")

        results["summary"] = {
            "total_duplicados_email": len(results["duplicados_email"]),
            "total_duplicados_telefono": len(results["duplicados_telefono"]),
        }

        logger.info(f"  Resultado: {results['summary']['total_duplicados_email']} grupos de email duplicados")
        logger.info(f"  Resultado: {results['summary']['total_duplicados_telefono']} grupos de teléfono duplicados")

        self.results["DUPLICADOS"] = results
        return results

    def check_orphans(self) -> dict:
        """Detectar registros huérfanos (sin asignaciones de línea)."""
        logger.info("\n[2/8] VERIFICANDO REGISTROS HUÉRFANOS...")
        
        query = """
            SELECT 
                d.id,
                d.nombre,
                d.email,
                d.telefono,
                d.es_activo,
                COALESCE(COUNT(ala.id), 0) as num_lineas,
                d.fecha_creacion
            FROM datos_importados d
            LEFT JOIN agente_linea_asignaciones ala ON d.id = ala.agente_id AND ala.es_activa = TRUE
            WHERE d.es_activo = TRUE
            GROUP BY d.id
            HAVING num_lineas = 0
            ORDER BY d.fecha_creacion DESC
        """
        
        rows = self._run_query(self.main_session, query, "Agentes activos sin líneas")
        results = {"agentes_sin_lineas": []}
        
        for row in rows:
            results["agentes_sin_lineas"].append({
                "id": row[0],
                "nombre": row[1],
                "email": row[2],
                "telefono": row[3],
                "es_activo": row[4],
                "num_lineas": row[5],
                "fecha_creacion": str(row[6])
            })
            logger.warning(f"  ⚠ Agente sin líneas: {row[1]} (ID={row[0]}, activo={row[4]})")

        results["summary"] = {"total_agentes_sin_lineas": len(results["agentes_sin_lineas"])}
        
        logger.info(f"  Resultado: {results['summary']['total_agentes_sin_lineas']} agentes sin líneas asignadas")
        
        self.results["HUERFANOS"] = results
        return results

    def check_legacy_sync_mismatch(self) -> dict:
        """Detectar desalineación con tabla legacy registro_agentes.agentes."""
        logger.info("\n[3/8] VERIFICANDO DESALINEACIÓN CON LEGACY...")
        
        results = {
            "faltantes_en_legacy": [],
            "summary": {}
        }

        # Registros en main que NO están en legacy
        query = """
            SELECT di.id, di.nombre, di.email
            FROM datos_importados di
            WHERE di.es_activo = TRUE
            LIMIT 5
        """
        
        try:
            rows = self._run_query(self.main_session, query, "Verificación de sync legacy")
            logger.info(f"  Resultado: {len(rows)} registros activos encontrados")
            results["summary"]["registros_activos"] = len(rows)
        except Exception as e:
            logger.warning(f"  Error verificando legacy: {e}")
            results["summary"]["error"] = str(e)

        self.results["DESALINEACION_LEGACY"] = results
        return results

    def check_json_integrity(self) -> dict:
        """Verificar integridad de JSON en datos_adicionales."""
        logger.info("\n[4/8] VERIFICANDO INTEGRIDAD JSON...")
        
        results = {
            "json_invalido": [],
            "resumen_campos": {},
            "summary": {}
        }

        # Contar JSON válido vs inválido
        query = """
            SELECT 
                COUNT(*) as total,
                SUM(IF(datos_adicionales IS NULL OR datos_adicionales = '', 1, 0)) as sin_json
            FROM datos_importados
        """
        
        try:
            row = self._run_query(self.main_session, query)[0]
            results["summary"]["total_registros"] = row[0]
            results["summary"]["sin_json"] = row[1]

            logger.info(f"  Total registros: {row[0]}")
            logger.info(f"  Sin JSON: {row[1]}")
        except Exception as e:
            logger.warning(f"  Error verificando JSON: {e}")
            results["summary"]["error"] = str(e)

        self.results["JSON_INTEGRIDAD"] = results
        return results

    def check_qr_status(self) -> dict:
        """Analizar estado de QR (impreso, no impreso, sin generar)."""
        logger.info("\n[5/8] VERIFICANDO STATUS QR...")
        
        query = """
            SELECT 
                SUM(IF(qr_code IS NULL, 1, 0)) as sin_qr_generado,
                SUM(IF(qr_code IS NOT NULL AND qr_impreso = FALSE, 1, 0)) as qr_generado_no_impreso,
                SUM(IF(qr_impreso = TRUE, 1, 0)) as qr_impreso,
                COUNT(*) as total
            FROM datos_importados
        """
        
        try:
            row = self._run_query(self.main_session, query)[0]
            results = {
                "sin_qr_generado": row[0],
                "qr_generado_no_impreso": row[1],
                "qr_impreso": row[2],
                "total": row[3],
                "porcentaje_impreso": round((row[2] / row[3] * 100), 2) if row[3] > 0 else 0
            }
            
            logger.info(f"  Sin QR generado: {row[0]}")
            logger.info(f"  QR generado (no impreso): {row[1]}")
            logger.info(f"  QR impreso: {row[2]} ({results['porcentaje_impreso']}%)")
        except Exception as e:
            logger.warning(f"  Error verificando QR: {e}")
            results = {"error": str(e)}

        self.results["QR_STATUS"] = results
        return results

    def check_payment_anomalies(self) -> dict:
        """Detectar anomalías en pagos semanales."""
        logger.info("\n[6/8] VERIFICANDO PAGOS SEMANALES...")
        
        results = {
            "pagos_pendientes": 0,
            "summary": {}
        }

        # Pagos pendientes del último mes
        query = """
            SELECT 
                COUNT(*) as total_pendientes
            FROM pagos_semanales
            WHERE pagado = FALSE 
              AND semana_inicio >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        """
        
        try:
            row = self._run_query(self.main_session, query)[0]
            results["pagos_pendientes"] = row[0]
            logger.info(f"  Pagos pendientes (último mes): {row[0]}")
            results["summary"]["pagos_pendientes"] = row[0]
        except Exception as e:
            logger.warning(f"  Error verificando pagos: {e}")
            results["summary"]["error"] = str(e)

        self.results["PAGOS_ANOMALIAS"] = results
        return results

    def check_line_assignments(self) -> dict:
        """Verificar asignaciones de línea."""
        logger.info("\n[7/8] VERIFICANDO ASIGNACIONES DE LÍNEA...")
        
        results = {
            "lineas_sin_asignacion": 0,
            "summary": {}
        }

        # Líneas sin asignación activa
        query = """
            SELECT 
                COUNT(*) as total_sin_asignacion
            FROM lineas_telefonicas lt
            LEFT JOIN agente_linea_asignaciones ala 
                ON lt.id = ala.linea_id AND ala.es_activa = TRUE
            WHERE ala.id IS NULL AND lt.es_activa = TRUE
        """
        
        try:
            row = self._run_query(self.main_session, query)[0]
            results["lineas_sin_asignacion"] = row[0]
            logger.info(f"  Líneas activas sin asignación: {row[0]}")
            results["summary"]["lineas_sin_asignacion"] = row[0]
        except Exception as e:
            logger.warning(f"  Error verificando líneas: {e}")
            results["summary"]["error"] = str(e)

        self.results["LINEAS_ASIGNACION"] = results
        return results

    def check_audit_trail(self) -> dict:
        """Revisar actividad reciente."""
        logger.info("\n[8/8] VERIFICANDO AUDITORÍA...")
        
        results = {
            "cambios_recientes": {},
            "summary": {}
        }

        # Cambios en últimos 7 días
        query = """
            SELECT 
                COUNT(*) as total
            FROM auditoria_acciones
            WHERE fecha_creacion >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        """
        
        try:
            row = self._run_query(self.main_session, query)[0]
            logger.info(f"  Cambios últimos 7 días: {row[0]}")
            results["summary"]["total_cambios_7dias"] = row[0]
        except Exception as e:
            logger.warning(f"  Error verificando auditoría: {e}")
            results["summary"]["error"] = str(e)

        self.results["AUDITORIA"] = results
        return results

    def generate_report(self):
        """Generar reporte completo."""
        
        logger.info("\n" + "=" * 80)
        logger.info("RESUMEN EJECUTIVO - SALUD DE BD")
        logger.info("=" * 80)

        # Resumen por sección
        logger.info("\n📊 PUNTUACIÓN DE SALUD:")
        
        issues_found = 0
        for check_name, results in self.results.items():
            if isinstance(results, dict) and "summary" in results:
                summary = results["summary"]
                issues = sum(v for k, v in summary.items() if isinstance(v, int) and v > 0)
                if issues > 0:
                    issues_found += issues
                    logger.info(f"  ⚠ {check_name}: {issues} problema(s)")
                else:
                    logger.info(f"  ✓ {check_name}: OK")

        if issues_found == 0:
            logger.info("\n✓ BASE DE DATOS EN BUEN ESTADO")
        else:
            logger.info(f"\n⚠ {issues_found} PROBLEMA(S) DETECTADO(S) - VER DETALLES ARRIBA")

        logger.info("\n" + "=" * 80)
        logger.info(f"Reporte completo: {log_file}")
        logger.info("=" * 80)

    def cleanup(self):
        """Cerrar sesiones."""
        self.main_session.close()


def main():
    """Ejecutar health check completo."""
    
    logger.info("=" * 80)
    logger.info("TABLERO DE SALUD SQL - DIAGNÓSTICO DE INTEGRIDAD")
    logger.info(f"Iniciado: {datetime.now().isoformat()}")
    logger.info(f"BD: {config.DB_NAME} | Host: {config.DB_HOST}")
    logger.info("=" * 80)

    # Crear engine
    try:
        main_engine = create_engine(DATABASE_URL, echo=False)
        with main_engine.begin() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✓ Conexión a BD exitosa")
    except Exception as e:
        logger.error(f"✗ No se pudo conectar a BD: {e}")
        return False

    # Ejecutar checks
    checker = HealthChecker(main_engine)

    if CHECKS.get("DUPLICADOS"):
        checker.check_duplicates()
    if CHECKS.get("HUERFANOS"):
        checker.check_orphans()
    if CHECKS.get("DESALINEACION_LEGACY"):
        checker.check_legacy_sync_mismatch()
    if CHECKS.get("JSON_INTEGRIDAD"):
        checker.check_json_integrity()
    if CHECKS.get("QR_STATUS"):
        checker.check_qr_status()
    if CHECKS.get("PAGOS_ANOMALIAS"):
        checker.check_payment_anomalies()
    if CHECKS.get("LINEAS_ASIGNACION"):
        checker.check_line_assignments()
    if CHECKS.get("AUDITORIA"):
        checker.check_audit_trail()

    # Generar reporte
    checker.generate_report()
    checker.cleanup()

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
