"""
Tablero de Salud SQL - Diagnóstico integral de integridad y coherencia BD

Consultas de diagnostico:
1. Duplicados por email/telefono
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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import Session, sessionmaker
import sys
import os

# Agregar app al path
sys.path.insert(0, str(Path(__file__).parent.parent))
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
LEGACY_DB_NAME = config.PBX_DB_NAME  # registro_agentes
LEGACY_DB_URL = f"mysql+mysqlconnector://{config.DB_USER}:{config.DB_PASSWORD}@{config.DB_HOST}:{config.DB_PORT}/{LEGACY_DB_NAME}"

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

    def __init__(self, main_engine, legacy_engine=None):
        self.main_engine = main_engine
        self.legacy_engine = legacy_engine
        self.main_session = sessionmaker(bind=main_engine)()
        self.legacy_session = sessionmaker(bind=legacy_engine)() if legacy_engine else None
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
        
        if not self.legacy_session:
            logger.warning("  ⚠ Base de datos legacy no configurada. Saltando check.")
            return {"error": "Legacy DB not configured", "summary": {}}

        results = {
            "faltantes_en_legacy": [],
            "faltantes_en_main": [],
            "desalineados": [],
            "summary": {}
        }

        # Registros en main que NO están en legacy
        query = """
            SELECT di.id, di.nombre, di.email
            FROM database_manager.datos_importados di
            LEFT JOIN registro_agentes.agentes ra ON di.id = ra.id
            WHERE ra.id IS NULL AND di.es_activo = TRUE
            LIMIT 100
        """
        
        try:
            rows = self._run_query(self.main_session, query, "Faltantes en legacy")
            for row in rows:
                results["faltantes_en_legacy"].append({
                    "id": row[0],
                    "nombre": row[1],
                    "email": row[2]
                })
                logger.warning(f"  ⚠ En main pero NO en legacy: {row[1]} (ID={row[0]})")
        except Exception as e:
            logger.warning(f"  Error verificando legacy: {e}")

        results["summary"] = {
            "faltantes_en_legacy": len(results["faltantes_en_legacy"]),
            "faltantes_en_main": len(results["faltantes_en_main"]),
            "desalineados": len(results["desalineados"]),
        }
        
        logger.info(f"  Resultado: {results['summary']['faltantes_en_legacy']} faltantes en legacy")
        
        self.results["DESALINEACION_LEGACY"] = results
        return results

    def check_json_integrity(self) -> dict:
        """Verificar integridad de JSON en datos_adicionales."""
        logger.info("\n[4/8] VERIFICANDO INTEGRIDAD JSON...")
        
        results = {
            "json_invalido": [],
            "json_vacio": 0,
            "resumen_campos": {},
            "summary": {}
        }

        # Contar JSON válido vs inválido
        query = """
            SELECT 
                COUNT(*) as total,
                SUM(IF(datos_adicionales IS NULL OR datos_adicionales = '', 1, 0)) as sin_json,
                SUM(IF(JSON_VALID(datos_adicionales) = 1, 1, 0)) as json_valido,
                SUM(IF(JSON_VALID(datos_adicionales) = 0 AND datos_adicionales IS NOT NULL, 1, 0)) as json_invalido
            FROM datos_importados
        """
        
        row = self._run_query(self.main_session, query)[0]
        results["summary"]["total_registros"] = row[0]
        results["summary"]["sin_json"] = row[1]
        results["summary"]["json_valido"] = row[2]
        results["summary"]["json_invalido"] = row[3]

        logger.info(f"  Total registros: {row[0]}")
        logger.info(f"  Sin JSON: {row[1]}")
        logger.info(f"  JSON válido: {row[2]}")
        logger.info(f"  JSON inválido: {row[3]}")

        # Obtener JSON invalido
        if row[3] > 0:
            query = """
                SELECT id, nombre, datos_adicionales
                FROM datos_importados
                WHERE datos_adicionales IS NOT NULL 
                  AND JSON_VALID(datos_adicionales) = 0
                LIMIT 20
            """
            
            rows = self._run_query(self.main_session, query, "JSON inválido")
            for r in rows:
                results["json_invalido"].append({
                    "id": r[0],
                    "nombre": r[1],
                    "datos_adicionales": r[2][:200] if r[2] else None
                })
                logger.warning(f"  ⚠ JSON inválido (ID={r[0]}): {r[2][:100] if r[2] else 'NULL'}")

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

        self.results["QR_STATUS"] = results
        return results

    def check_payment_anomalies(self) -> dict:
        """Detectar anomalías en pagos semanales."""
        logger.info("\n[6/8] VERIFICANDO PAGOS SEMANALES...")
        
        results = {
            "pagos_pendientes": 0,
            "pagos_sem_agente": [],
            "pagos_sin_linea": [],
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
        
        row = self._run_query(self.main_session, query)[0]
        results["pagos_pendientes"] = row[0]
        logger.info(f"  Pagos pendientes (último mes): {row[0]}")

        # Pagos de agentes que no existen
        query = """
            SELECT ps.id, ps.agente_id, ps.semana_inicio, ps.monto
            FROM pagos_semanales ps
            LEFT JOIN datos_importados di ON ps.agente_id = di.id
            WHERE di.id IS NULL
            LIMIT 50
        """
        
        rows = self._run_query(self.main_session, query, "Pagos de agentes inexistentes")
        for row in rows:
            results["pagos_sem_agente"].append({
                "id": row[0],
                "agente_id": row[1],
                "semana": str(row[2]),
                "monto": float(row[3]) if row[3] else 0
            })
            logger.warning(f"  ⚠ Pago de agente inexistente: agente_id={row[1]}")

        results["summary"] = {
            "pagos_pendientes": results["pagos_pendientes"],
            "pagos_de_agentes_inexistentes": len(results["pagos_sem_agente"])
        }

        self.results["PAGOS_ANOMALIAS"] = results
        return results

    def check_line_assignments(self) -> dict:
        """Verificar asignaciones de línea."""
        logger.info("\n[7/8] VERIFICANDO ASIGNACIONES DE LÍNEA...")
        
        results = {
            "lineas_sin_asignacion": 0,
            "asignaciones_agente_inexistente": [],
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
        
        row = self._run_query(self.main_session, query)[0]
        results["lineas_sin_asignacion"] = row[0]
        logger.info(f"  Líneas activas sin asignación: {row[0]}")

        # Asignaciones a agentes inexistentes
        query = """
            SELECT ala.id, ala.agente_id, ala.linea_id, lt.numero
            FROM agente_linea_asignaciones ala
            LEFT JOIN datos_importados di ON ala.agente_id = di.id
            LEFT JOIN lineas_telefonicas lt ON ala.linea_id = lt.id
            WHERE di.id IS NULL
            LIMIT 50
        """
        
        rows = self._run_query(self.main_session, query, "Asignaciones a agentes inexistentes")
        for row in rows:
            results["asignaciones_agente_inexistente"].append({
                "asignacion_id": row[0],
                "agente_id": row[1],
                "linea_id": row[2],
                "numero": row[3]
            })
            logger.warning(f"  ⚠ Asignación de línea a agente inexistente: agente_id={row[1]}")

        results["summary"] = {
            "lineas_sin_asignacion": results["lineas_sin_asignacion"],
            "asignaciones_agente_inexistente": len(results["asignaciones_agente_inexistente"])
        }

        self.results["LINEAS_ASIGNACION"] = results
        return results

    def check_audit_trail(self) -> dict:
        """Revisar actividad reciente y cambios sospechosos."""
        logger.info("\n[8/8] VERIFICANDO AUDITORÍA...")
        
        results = {
            "cambios_recientes": {},
            "cambios_por_usuario": {},
            "summary": {}
        }

        # Cambios en últimos 7 días
        query = """
            SELECT 
                aa.tipo_accion,
                COUNT(*) as cantidad
            FROM auditoria_acciones aa
            WHERE aa.fecha_creacion >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            GROUP BY aa.tipo_accion
            ORDER BY cantidad DESC
        """
        
        rows = self._run_query(self.main_session, query, "Cambios últimos 7 días")
        for row in rows:
            results["cambios_recientes"][row[0]] = row[1]
            logger.info(f"  {row[0]}: {row[1]} cambios")

        # Cambios por usuario
        query = """
            SELECT 
                u.username,
                COUNT(*) as cantidad
            FROM auditoria_acciones aa
            JOIN usuarios u ON aa.usuario_id = u.id
            WHERE aa.fecha_creacion >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            GROUP BY u.username
            ORDER BY cantidad DESC
        """
        
        rows = self._run_query(self.main_session, query, "Cambios por usuario")
        for row in rows:
            results["cambios_por_usuario"][row[0]] = row[1]
            logger.info(f"  Usuario '{row[0]}': {row[1]} cambios")

        results["summary"]["total_cambios_7dias"] = sum(results["cambios_recientes"].values())

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
        if self.legacy_session:
            self.legacy_session.close()


def main():
    """Ejecutar health check completo."""
    
    logger.info("=" * 80)
    logger.info("TABLERO DE SALUD SQL - DIAGNÓSTICO DE INTEGRIDAD")
    logger.info(f"Iniciado: {datetime.now().isoformat()}")
    logger.info("=" * 80)

    # Crear engines
    try:
        main_engine = create_engine(DATABASE_URL, echo=False)
        with main_engine.begin() as conn:
            conn.execute(text("SELECT 1"))  # Test
        logger.info("✓ Conexión a BD principal exitosa")
    except Exception as e:
        logger.error(f"✗ No se pudo conectar a BD principal: {e}")
        return False

    # Intentar conexión a legacy (opcional)
    legacy_engine = None
    try:
        legacy_engine = create_engine(LEGACY_DB_URL, echo=False)
        with legacy_engine.begin() as conn:
            conn.execute(text("SELECT 1"))  # Test
        logger.info("✓ Conexión a BD legacy exitosa")
    except Exception:
        logger.warning("⚠ BD legacy no disponible - Algunos checks serán saltados")

    # Ejecutar checks
    checker = HealthChecker(main_engine, legacy_engine)

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
    import sys
    success = main()
    sys.exit(0 if success else 1)
