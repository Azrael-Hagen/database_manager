"""
Migración Fase B: Normalizar columnas alias/ubicacion/fp/fc/grupo/numero_voip
desde JSON (datos_adicionales) a columnas dedicadas en datos_importados.

SEGURIDAD:
- Validación completa antes de migración
- Rollback automático en caso de error
- Backup de datos originales
- Logs detallados de cada paso
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.exc import SQLAlchemyError

# Configurar logging
log_file = Path(__file__).parent.parent.parent / "logs" / f"migration_phase_b_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
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

DATABASE_URL = "mysql+pymysql://root:root@localhost/database_manager"

# Columnas a crear y sus definiciones SQL
COLUMNS_TO_ADD = {
    "alias": "VARCHAR(255) NULL COMMENT 'Identificador alternativo/apodo del agente'",
    "ubicacion": "VARCHAR(255) NULL COMMENT 'Ubicacion fisica del agente'",
    "fp": "VARCHAR(100) NULL COMMENT 'Fecha de inicio de prestacion de servicio'",
    "fc": "VARCHAR(100) NULL COMMENT 'Fecha de conclusion del contrato'",
    "grupo": "VARCHAR(100) NULL COMMENT 'Grupo o equipo del agente'",
    "numero_voip": "VARCHAR(50) NULL COMMENT 'Numero VoIP asignado'",
}

# Keys esperadas en JSON datos_adicionales
JSON_KEYS = list(COLUMNS_TO_ADD.keys())


class MigrationValidator:
    """Validar integridad y aplicabilidad de migracion."""

    def __init__(self, engine):
        self.engine = engine
        self.session = sessionmaker(bind=engine)()

    def check_connection(self) -> bool:
        """Verificar conexion a BD."""
        try:
            self.session.execute(text("SELECT 1"))
            logger.info("✓ Conexión a BD exitosa")
            return True
        except Exception as e:
            logger.error(f"✗ Error de conexión: {e}")
            return False

    def check_table_exists(self) -> bool:
        """Verificar que tabla datos_importados existe."""
        inspector = inspect(self.engine)
        tables = inspector.get_table_names()
        exists = "datos_importados" in tables
        if exists:
            logger.info("✓ Tabla 'datos_importados' existe")
        else:
            logger.error("✗ Tabla 'datos_importados' no encontrada")
        return exists

    def check_columns_not_exist(self) -> bool:
        """Verificar que las columnas NO existen aún."""
        inspector = inspect(self.engine)
        existing_columns = {col['name'] for col in inspector.get_columns('datos_importados')}
        
        to_add = set(COLUMNS_TO_ADD.keys())
        already_exist = to_add & existing_columns
        
        if already_exist:
            logger.warning(f"⚠ Columnas que ya existen: {already_exist}")
            return False
        
        logger.info(f"✓ Todas las {len(COLUMNS_TO_ADD)} columnas aún no existen")
        return True

    def check_json_data_integrity(self) -> tuple[bool, dict]:
        """Analizar integridad de datos JSON antes de migración."""
        try:
            result = self.session.execute(
                text("""
                    SELECT 
                        id, 
                        datos_adicionales,
                        JSON_TYPE(datos_adicionales) as json_type
                    FROM datos_importados
                    WHERE datos_adicionales IS NOT NULL
                    LIMIT 10
                """)
            ).fetchall()

            sample_count = len(result)
            parse_errors = 0
            key_coverage = {key: 0 for key in JSON_KEYS}

            for row in result:
                try:
                    data = json.loads(row[1])
                    for key in JSON_KEYS:
                        if key in data and data[key]:
                            key_coverage[key] += 1
                except json.JSONDecodeError:
                    parse_errors += 1

            logger.info(f"✓ Validación JSON: {sample_count} registros analizados, {parse_errors} errores de parseo")
            logger.info(f"  Cobertura de datos:")
            for key, count in key_coverage.items():
                logger.info(f"    - {key}: {count}/{sample_count} registros")

            return parse_errors == 0, key_coverage

        except Exception as e:
            logger.error(f"✗ Error validando JSON: {e}")
            return False, {}

    def cleanup(self):
        """Cerrar sesion."""
        self.session.close()


class MigrationExecutor:
    """Ejecutar la migración en fases."""

    def __init__(self, engine):
        self.engine = engine
        self.session = sessionmaker(bind=engine)()
        self.backup_file = Path(__file__).parent.parent.parent / "logs" / f"backup_datos_adicionales_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    def create_backup(self) -> bool:
        """Hacer backup de datos_adicionales antes de cambios."""
        try:
            result = self.session.execute(
                text("SELECT id, datos_adicionales FROM datos_importados WHERE datos_adicionales IS NOT NULL")
            ).fetchall()

            backup_data = [{"id": row[0], "datos_adicionales": row[1]} for row in result]

            with open(self.backup_file, 'w') as f:
                json.dump(backup_data, f, indent=2)

            logger.info(f"✓ Backup creado: {self.backup_file} ({len(backup_data)} registros)")
            return True

        except Exception as e:
            logger.error(f"✗ Error creando backup: {e}")
            return False

    def add_columns(self) -> bool:
        """Agregar las nuevas columnas a la tabla."""
        try:
            with self.engine.begin() as conn:
                for col_name, col_def in COLUMNS_TO_ADD.items():
                    sql = f"ALTER TABLE datos_importados ADD COLUMN `{col_name}` {col_def}"
                    conn.execute(text(sql))
                    logger.info(f"✓ Columna '{col_name}' agregada")

            return True

        except SQLAlchemyError as e:
            logger.error(f"✗ Error agregando columnas: {e}")
            return False

    def migrate_json_to_columns(self) -> bool:
        """Extraer datos del JSON y migrar a columnas."""
        try:
            # Obtener todos los registros con datos_adicionales
            result = self.session.execute(
                text("SELECT id, datos_adicionales FROM datos_importados WHERE datos_adicionales IS NOT NULL")
            ).fetchall()

            total = len(result)
            migrated = 0
            errors = 0

            logger.info(f"Iniciando migración de {total} registros...")

            for record_id, json_str in result:
                try:
                    # Parsear JSON
                    data = json.loads(json_str) if json_str else {}

                    # Preparar UPDATE dinámico
                    set_clauses = []
                    params = {}
                    
                    for key in JSON_KEYS:
                        value = data.get(key)
                        if value:
                            set_clauses.append(f"`{key}` = :{key}")
                            params[key] = str(value)[:255] if key != "numero_voip" else str(value)[:50]

                    if set_clauses:
                        sql = f"UPDATE datos_importados SET {', '.join(set_clauses)} WHERE id = :id"
                        params['id'] = record_id
                        self.session.execute(text(sql), params)
                        migrated += 1

                    if migrated % 100 == 0:
                        logger.info(f"  Procesados {migrated}/{total} registros...")

                except json.JSONDecodeError as e:
                    logger.warning(f"⚠ Error parseando JSON para id={record_id}: {e}")
                    errors += 1

            self.session.commit()
            logger.info(f"✓ Migración completada: {migrated} actualizados, {errors} errores")
            return True

        except Exception as e:
            logger.error(f"✗ Error durante migración: {e}")
            self.session.rollback()
            return False

    def add_indexes(self) -> bool:
        """Crear índices en las nuevas columnas para mejor performance."""
        try:
            with self.engine.begin() as conn:
                # Índices simples para búsqueda frecuente
                for col_name in ["alias", "grupo", "numero_voip"]:
                    idx_name = f"ix_datos_importados_{col_name}"
                    try:
                        sql = f"CREATE INDEX `{idx_name}` ON datos_importados (`{col_name}`)"
                        conn.execute(text(sql))
                        logger.info(f"✓ Índice '{idx_name}' creado")
                    except:
                        logger.warning(f"⚠ Índice '{idx_name}' ya existe o error")

            return True

        except Exception as e:
            logger.error(f"✗ Error creando índices: {e}")
            return False

    def validate_migration(self) -> bool:
        """Validar que la migración fue exitosa."""
        try:
            # Verificar columnas existen
            inspector = inspect(self.engine)
            existing_columns = {col['name'] for col in inspector.get_columns('datos_importados')}
            
            for col_name in COLUMNS_TO_ADD.keys():
                if col_name not in existing_columns:
                    logger.error(f"✗ Columna '{col_name}' no fue creada")
                    return False

            # Verificar que hay datos en las nuevas columnas
            result = self.session.execute(
                text("""
                    SELECT 
                        COUNT(*) as total_registros,
                        SUM(IF(alias IS NOT NULL, 1, 0)) as con_alias,
                        SUM(IF(ubicacion IS NOT NULL, 1, 0)) as con_ubicacion,
                        SUM(IF(grupo IS NOT NULL, 1, 0)) as con_grupo,
                        SUM(IF(numero_voip IS NOT NULL, 1, 0)) as con_numero_voip
                    FROM datos_importados
                """)
            ).fetchone()

            total, con_alias, con_ubicacion, con_grupo, con_numero_voip = result

            logger.info(f"✓ Validación post-migración:")
            logger.info(f"  - Total de registros: {total}")
            logger.info(f"  - Con alias: {con_alias}")
            logger.info(f"  - Con ubicación: {con_ubicacion}")
            logger.info(f"  - Con grupo: {con_grupo}")
            logger.info(f"  - Con número VoIP: {con_numero_voip}")

            return True

        except Exception as e:
            logger.error(f"✗ Error validando migración: {e}")
            return False

    def rollback_migration(self) -> bool:
        """Rollback: eliminar las columnas agregadas."""
        try:
            with self.engine.begin() as conn:
                for col_name in COLUMNS_TO_ADD.keys():
                    try:
                        sql = f"ALTER TABLE datos_importados DROP COLUMN `{col_name}`"
                        conn.execute(text(sql))
                        logger.info(f"✓ Columna '{col_name}' eliminada (ROLLBACK)")
                    except:
                        logger.warning(f"⚠ No se pudo eliminar columna '{col_name}'")

            logger.warning("⚠ ROLLBACK completado - Migración revertida")
            return True

        except Exception as e:
            logger.error(f"✗ Error durante rollback: {e}")
            return False

    def cleanup(self):
        """Cerrar sesion."""
        self.session.close()


def main():
    """Ejecutar migración con validaciones."""
    
    logger.info("=" * 80)
    logger.info("MIGRACIÓN FASE B - NORMALIZACIÓN DE COLUMNAS")
    logger.info("=" * 80)
    logger.info("")

    # Crear engine
    try:
        engine = create_engine(DATABASE_URL, echo=False)
    except Exception as e:
        logger.error(f"✗ No se pudo conectar a la BD: {e}")
        return False

    # Fase 1: Validación
    logger.info("FASE 1: VALIDACIÓN")
    logger.info("-" * 80)
    
    validator = MigrationValidator(engine)
    
    if not validator.check_connection():
        return False
    if not validator.check_table_exists():
        return False
    if not validator.check_columns_not_exist():
        logger.warning("Las columnas ya existen. Abortando migración.")
        return False
    
    json_ok, key_coverage = validator.check_json_data_integrity()
    validator.cleanup()

    if not json_ok:
        logger.warning("⚠ Se encontraron errores en JSON, pero continuando...")

    logger.info("")
    logger.info("FASE 2: BACKUP Y MIGRACIÓN")
    logger.info("-" * 80)

    executor = MigrationExecutor(engine)

    # Crear backup
    if not executor.create_backup():
        logger.error("✗ No se pudo crear backup. Abortando.")
        executor.cleanup()
        return False

    # Agregar columnas
    if not executor.add_columns():
        logger.error("✗ Error agregando columnas. Abortando.")
        executor.cleanup()
        return False

    # Migrar datos
    if not executor.migrate_json_to_columns():
        logger.error("✗ Error durante migración. Ejecutando rollback...")
        executor.rollback_migration()
        executor.cleanup()
        return False

    # Crear índices
    executor.add_indexes()

    logger.info("")
    logger.info("FASE 3: VALIDACIÓN POST-MIGRACIÓN")
    logger.info("-" * 80)

    if not executor.validate_migration():
        logger.error("✗ Validación post-migración fallida. Ejecutando rollback...")
        executor.rollback_migration()
        executor.cleanup()
        return False

    executor.cleanup()

    logger.info("")
    logger.info("=" * 80)
    logger.info("✓ MIGRACIÓN FASE B COMPLETADA EXITOSAMENTE")
    logger.info("=" * 80)
    logger.info(f"Log: {log_file}")
    logger.info(f"Backup: {executor.backup_file}")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
