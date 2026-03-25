"""Base de datos mejorada usando SQLAlchemy ORM."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import logging
import re
from app.config import config
from app.models import Base

ROLE_ADMIN = "admin"
ROLE_VIEWER = "viewer"

logger = logging.getLogger(__name__)

# Configurar engine
engine = create_engine(
    config.DATABASE_URL,
    echo=config.API_DEBUG,
    pool_pre_ping=True,  # Verificar conexión antes de usar
    pool_recycle=3600,   # Reciclar conexiones cada hora
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _column_exists(connection, table_name: str, column_name: str) -> bool:
    return bool(
        connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE table_schema = DATABASE()
                  AND table_name = :table_name
                  AND column_name = :column_name
                """
            ),
            {"table_name": table_name, "column_name": column_name},
        ).scalar()
    )


def _index_exists(connection, table_name: str, index_name: str) -> bool:
    return bool(
        connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM information_schema.statistics
                WHERE table_schema = DATABASE()
                  AND table_name = :table_name
                  AND index_name = :index_name
                """
            ),
            {"table_name": table_name, "index_name": index_name},
        ).scalar()
    )


def _table_columns(connection, table_name: str) -> set[str]:
    rows = connection.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = :table_name
            """
        ),
        {"table_name": table_name},
    ).fetchall()
    return {str(row[0]) for row in rows}


def _execute_optional(connection, sql: str, params: dict | None = None, label: str = ""):
    try:
        connection.execute(text(sql), params or {})
    except Exception as exc:
        if label:
            logger.warning("Se omitio ajuste opcional [%s]: %s", label, exc)
        else:
            logger.warning("Se omitio ajuste opcional: %s", exc)


def _safe_identifier(raw: str | None, fallback: str) -> str:
    value = str(raw or "").strip() or fallback
    if not re.match(r"^[0-9A-Za-z_]+$", value):
        return fallback
    return value


def _col_or_default(alias: str, col_name: str, available: set[str], default_sql: str = "NULL") -> str:
    if col_name in available:
        return f"{alias}.`{col_name}`"
    return default_sql


def _build_vw_agentes_qr_estado_sql(agent_cols: set[str]) -> str:
    uuid_expr = _col_or_default("d", "uuid", agent_cols)
    nombre_expr = _col_or_default("d", "nombre", agent_cols, "''")
    telefono_expr = _col_or_default("d", "telefono", agent_cols)
    fecha_creacion_expr = _col_or_default("d", "fecha_creacion", agent_cols, "CURRENT_TIMESTAMP")
    es_activo_expr = f"COALESCE({_col_or_default('d', 'es_activo', agent_cols, '1')}, 1)"

    if "qr_filename" in agent_cols:
        tiene_qr_expr = "CASE WHEN d.`qr_filename` IS NOT NULL AND d.`qr_filename` <> '' THEN 1 ELSE 0 END"
    else:
        tiene_qr_expr = "0"

    return f"""
        CREATE OR REPLACE VIEW vw_agentes_qr_estado AS
        SELECT
            d.`id` AS id,
            {uuid_expr} AS uuid,
            {nombre_expr} AS nombre,
            {telefono_expr} AS telefono,
            {es_activo_expr} AS es_activo,
            {tiene_qr_expr} AS tiene_qr,
            {fecha_creacion_expr} AS fecha_creacion
        FROM agentes_operativos d
    """


def _build_vw_agentes_extensiones_pago_actual_sql(agent_cols: set[str]) -> str:
    uuid_expr = _col_or_default("d", "uuid", agent_cols)
    nombre_expr = _col_or_default("d", "nombre", agent_cols, "''")
    es_activo_expr = f"COALESCE({_col_or_default('d', 'es_activo', agent_cols, '1')}, 1)"
    where_es_activo_expr = es_activo_expr

    return f"""
        CREATE OR REPLACE VIEW vw_agentes_extensiones_pago_actual AS
        SELECT
            d.id AS agente_id,
            {uuid_expr} AS uuid,
            {nombre_expr} AS nombre,
            {es_activo_expr} AS es_activo,
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
                WHEN p.id IS NULL OR COALESCE(p.pagado, 0) = 0 THEN 'DEBE'
                ELSE 'PAGADO'
            END AS estado_pago
        FROM agentes_operativos d
        LEFT JOIN agente_linea_asignaciones ala
            ON ala.agente_id = d.id AND ala.es_activa = 1
        LEFT JOIN lineas_telefonicas l
            ON l.id = ala.linea_id AND COALESCE(l.es_activa, 1) = 1
        LEFT JOIN pagos_semanales p
            ON p.agente_id = d.id
           AND p.semana_inicio = DATE_SUB(CURDATE(), INTERVAL WEEKDAY(CURDATE()) DAY)
        WHERE {where_es_activo_expr} = 1
    """


def _build_vw_agentes_operacion_actual_sql(agent_cols: set[str]) -> str:
    uuid_expr = _col_or_default("d", "uuid", agent_cols)
    nombre_expr = _col_or_default("d", "nombre", agent_cols, "''")
    telefono_expr = _col_or_default("d", "telefono", agent_cols)
    email_expr = _col_or_default("d", "email", agent_cols)
    estatus_codigo_expr = _col_or_default("d", "estatus_codigo", agent_cols)
    es_activo_expr = f"COALESCE({_col_or_default('d', 'es_activo', agent_cols, '1')}, 1)"

    has_datos_adicionales = "datos_adicionales" in agent_cols
    alias_expr = "JSON_UNQUOTE(JSON_EXTRACT(d.datos_adicionales, '$.alias'))" if has_datos_adicionales else "NULL"
    ubicacion_expr = "JSON_UNQUOTE(JSON_EXTRACT(d.datos_adicionales, '$.ubicacion'))" if has_datos_adicionales else "NULL"
    grupo_expr = "JSON_UNQUOTE(JSON_EXTRACT(d.datos_adicionales, '$.grupo'))" if has_datos_adicionales else "NULL"
    voip_expr = "JSON_UNQUOTE(JSON_EXTRACT(d.datos_adicionales, '$.numero_voip'))" if has_datos_adicionales else "NULL"

    has_estatus_codigo = "estatus_codigo" in agent_cols
    estatus_nombre_expr = "s.nombre" if has_estatus_codigo else "NULL"
    estatus_operativo_expr = "COALESCE(s.es_operativo, 1)" if has_estatus_codigo else "1"
    estatus_join = "LEFT JOIN cat_estatus_agente s ON s.codigo = d.estatus_codigo" if has_estatus_codigo else ""

    return f"""
        CREATE OR REPLACE VIEW vw_agentes_operacion_actual AS
        SELECT
            d.id AS agente_id,
            {uuid_expr} AS uuid,
            {nombre_expr} AS nombre,
            {telefono_expr} AS telefono,
            {email_expr} AS email,
            {estatus_codigo_expr} AS estatus_codigo,
            {estatus_nombre_expr} AS estatus_nombre,
            {estatus_operativo_expr} AS estatus_operativo,
            {alias_expr} AS alias,
            {ubicacion_expr} AS ubicacion,
            {grupo_expr} AS grupo,
            {voip_expr} AS numero_voip,
            l.id AS linea_id,
            l.numero AS linea_numero,
            l.tipo AS linea_tipo,
            CASE
                WHEN ala.id IS NULL OR l.id IS NULL THEN 'SIN_LINEA'
                ELSE 'ASIGNADA'
            END AS linea_estado,
            p.semana_inicio,
            COALESCE(p.pagado, 0) AS pagado_semana,
            COALESCE(p.monto, 0) AS monto_semana,
            p.fecha_pago,
            CASE
                WHEN p.id IS NULL OR COALESCE(p.pagado, 0) = 0 THEN 'DEBE'
                ELSE 'PAGADO'
            END AS estado_pago
        FROM agentes_operativos d
        {estatus_join}
        LEFT JOIN agente_linea_asignaciones ala
            ON ala.agente_id = d.id AND ala.es_activa = 1
        LEFT JOIN lineas_telefonicas l
            ON l.id = ala.linea_id AND COALESCE(l.es_activa, 1) = 1
        LEFT JOIN pagos_semanales p
            ON p.agente_id = d.id
           AND p.semana_inicio = DATE_SUB(CURDATE(), INTERVAL WEEKDAY(CURDATE()) DAY)
        WHERE {es_activo_expr} = 1
    """


def _build_vw_pagos_pendientes_sql(agent_cols: set[str]) -> str:
    nombre_expr = _col_or_default("d", "nombre", agent_cols, "''")
    return f"""
        CREATE OR REPLACE VIEW vw_pagos_pendientes AS
        SELECT
            p.id,
            p.agente_id,
            {nombre_expr} AS nombre,
            p.telefono,
            p.numero_voip,
            p.semana_inicio,
            p.monto,
            p.pagado,
            p.fecha_pago,
            CASE WHEN a.id IS NULL THEN 0 ELSE 1 END AS alerta_emitida
        FROM pagos_semanales p
        LEFT JOIN agentes_operativos d ON d.id = p.agente_id
        LEFT JOIN alertas_pago a
            ON a.agente_id = p.agente_id
           AND a.semana_inicio = p.semana_inicio
           AND a.atendida = 0
        WHERE COALESCE(p.pagado, 0) = 0
    """


def get_useful_views_sql_map(connection) -> dict[str, str]:
    agent_cols = _table_columns(connection, "agentes_operativos")
    return {
        "vw_agentes_qr_estado": _build_vw_agentes_qr_estado_sql(agent_cols),
        "vw_usuarios_roles": """
            CREATE OR REPLACE VIEW vw_usuarios_roles AS
            SELECT
                id,
                username,
                email,
                nombre_completo,
                rol,
                es_activo,
                fecha_creacion,
                fecha_ultima_sesion
            FROM usuarios
        """,
        "vw_pagos_pendientes": _build_vw_pagos_pendientes_sql(agent_cols),
        "vw_agentes_extensiones_pago_actual": _build_vw_agentes_extensiones_pago_actual_sql(agent_cols),
        "vw_agentes_operacion_actual": _build_vw_agentes_operacion_actual_sql(agent_cols),
    }


def init_db():
    """Crear todas las tablas."""
    try:
        Base.metadata.create_all(bind=engine)
        _ensure_core_schema_updates()
        logger.info("Tablas de base de datos creadas/verificadas")
    except Exception as e:
        logger.error(f"Error creando tablas: {e}")
        raise


def _ensure_core_schema_updates():
    """Aplicar ajustes de esquema ligeros requeridos por nuevas funciones."""
    with engine.begin() as connection:
        role_column_exists = _column_exists(connection, "usuarios", "rol")
        if not role_column_exists:
            connection.execute(text("ALTER TABLE `usuarios` ADD COLUMN `rol` VARCHAR(20) NOT NULL DEFAULT 'viewer'"))
            connection.execute(text("CREATE INDEX `ix_usuarios_rol` ON `usuarios` (`rol`)"))

        if not _column_exists(connection, "usuarios", "es_temporal"):
            connection.execute(text("ALTER TABLE `usuarios` ADD COLUMN `es_temporal` TINYINT(1) NOT NULL DEFAULT 0"))
        if not _column_exists(connection, "usuarios", "temporal_expira_en"):
            connection.execute(text("ALTER TABLE `usuarios` ADD COLUMN `temporal_expira_en` DATETIME NULL"))
        if not _column_exists(connection, "usuarios", "temporal_renovaciones"):
            connection.execute(text("ALTER TABLE `usuarios` ADD COLUMN `temporal_renovaciones` INT NOT NULL DEFAULT 0"))
        if not _column_exists(connection, "usuarios", "solicitud_permiso_estado"):
            connection.execute(text("ALTER TABLE `usuarios` ADD COLUMN `solicitud_permiso_estado` VARCHAR(20) NOT NULL DEFAULT 'none'"))
        if not _column_exists(connection, "usuarios", "solicitud_permiso_rol"):
            connection.execute(text("ALTER TABLE `usuarios` ADD COLUMN `solicitud_permiso_rol` VARCHAR(20) NULL"))
        if not _column_exists(connection, "usuarios", "solicitud_permiso_motivo"):
            connection.execute(text("ALTER TABLE `usuarios` ADD COLUMN `solicitud_permiso_motivo` TEXT NULL"))
        if not _column_exists(connection, "usuarios", "solicitud_permiso_fecha"):
            connection.execute(text("ALTER TABLE `usuarios` ADD COLUMN `solicitud_permiso_fecha` DATETIME NULL"))

        if not _index_exists(connection, "usuarios", "ix_usuarios_es_temporal"):
            connection.execute(text("CREATE INDEX `ix_usuarios_es_temporal` ON `usuarios` (`es_temporal`)"))
        if not _index_exists(connection, "usuarios", "ix_usuarios_temporal_expira_en"):
            connection.execute(text("CREATE INDEX `ix_usuarios_temporal_expira_en` ON `usuarios` (`temporal_expira_en`)"))
        if not _index_exists(connection, "usuarios", "ix_usuarios_solicitud_permiso_estado"):
            connection.execute(text("CREATE INDEX `ix_usuarios_solicitud_permiso_estado` ON `usuarios` (`solicitud_permiso_estado`)"))

        agent_cols = _table_columns(connection, "agentes_operativos")

        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS `temp_usuarios_historial` (
                    `id` INT NOT NULL AUTO_INCREMENT,
                    `usuario_id` INT NOT NULL,
                    `username` VARCHAR(50) NOT NULL,
                    `email` VARCHAR(255) NULL,
                    `rol` VARCHAR(20) NOT NULL DEFAULT 'viewer',
                    `fecha_creacion_usuario` DATETIME NULL,
                    `fecha_expiracion` DATETIME NULL,
                    `fecha_eliminacion` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    `motivo` VARCHAR(80) NOT NULL DEFAULT 'expirado',
                    `eliminado_por` INT NULL,
                    `detalle_json` TEXT NULL,
                    PRIMARY KEY (`id`),
                    KEY `ix_temp_usuarios_historial_usuario_fecha` (`usuario_id`, `fecha_eliminacion`),
                    KEY `ix_temp_usuarios_historial_username` (`username`),
                    KEY `ix_temp_usuarios_historial_motivo` (`motivo`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
        )

        # Asegurar que papelera_registros existe aunque ya se cree con create_all
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS `papelera_registros` (
                    `id` INT NOT NULL AUTO_INCREMENT,
                    `tabla` VARCHAR(80) NOT NULL,
                    `registro_id` INT NOT NULL,
                    `snapshot_json` TEXT NOT NULL,
                    `tipo_borrado` VARCHAR(20) NOT NULL DEFAULT 'soft',
                    `borrado_por` INT NULL,
                    `fecha_borrado` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    `restaurado` TINYINT(1) NOT NULL DEFAULT 0,
                    `fecha_restauracion` DATETIME NULL,
                    `restaurado_por` INT NULL,
                    PRIMARY KEY (`id`),
                    KEY `ix_papelera_tabla_id` (`tabla`, `registro_id`),
                    KEY `ix_papelera_fecha` (`fecha_borrado`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
        )

        if "estatus_codigo" in agent_cols and not _index_exists(connection, "agentes_operativos", "ix_agentes_operativos_estatus_codigo"):
            connection.execute(text("CREATE INDEX `ix_agentes_operativos_estatus_codigo` ON `agentes_operativos` (`estatus_codigo`)"))

        if "es_activo" in agent_cols and "nombre" in agent_cols and not _index_exists(connection, "agentes_operativos", "ix_agentes_operativos_activo_nombre"):
            connection.execute(text("CREATE INDEX `ix_agentes_operativos_activo_nombre` ON `agentes_operativos` (`es_activo`, `nombre`)"))

        if not _index_exists(connection, "agente_linea_asignaciones", "ix_agente_linea_asignaciones_agente_activa"):
            connection.execute(
                text(
                    "CREATE INDEX `ix_agente_linea_asignaciones_agente_activa` ON `agente_linea_asignaciones` (`agente_id`, `es_activa`)"
                )
            )

        if not _index_exists(connection, "agente_linea_asignaciones", "ix_agente_linea_asignaciones_linea_activa"):
            connection.execute(
                text(
                    "CREATE INDEX `ix_agente_linea_asignaciones_linea_activa` ON `agente_linea_asignaciones` (`linea_id`, `es_activa`)"
                )
            )

        if not _column_exists(connection, "lineas_telefonicas", "categoria_linea"):
            connection.execute(
                text(
                    "ALTER TABLE `lineas_telefonicas` ADD COLUMN `categoria_linea` VARCHAR(20) NOT NULL DEFAULT 'NO_DEFINIDA'"
                )
            )

        if not _column_exists(connection, "lineas_telefonicas", "estado_conexion"):
            connection.execute(
                text(
                    "ALTER TABLE `lineas_telefonicas` ADD COLUMN `estado_conexion` VARCHAR(20) NOT NULL DEFAULT 'DESCONOCIDA'"
                )
            )

        if not _column_exists(connection, "lineas_telefonicas", "fecha_ultimo_uso"):
            connection.execute(
                text(
                    "ALTER TABLE `lineas_telefonicas` ADD COLUMN `fecha_ultimo_uso` DATETIME NULL"
                )
            )

        if not _index_exists(connection, "lineas_telefonicas", "ix_lineas_telefonicas_categoria_linea"):
            connection.execute(text("CREATE INDEX `ix_lineas_telefonicas_categoria_linea` ON `lineas_telefonicas` (`categoria_linea`)"))

        if not _index_exists(connection, "lineas_telefonicas", "ix_lineas_telefonicas_estado_conexion"):
            connection.execute(text("CREATE INDEX `ix_lineas_telefonicas_estado_conexion` ON `lineas_telefonicas` (`estado_conexion`)"))

        if not _column_exists(connection, "agente_linea_asignaciones", "cobro_desde_semana"):
            connection.execute(
                text(
                    "ALTER TABLE `agente_linea_asignaciones` ADD COLUMN `cobro_desde_semana` DATE NULL"
                )
            )

        if not _column_exists(connection, "agente_linea_asignaciones", "cargo_inicial"):
            connection.execute(
                text(
                    "ALTER TABLE `agente_linea_asignaciones` ADD COLUMN `cargo_inicial` DECIMAL(10,2) NOT NULL DEFAULT 0"
                )
            )

        if "qr_impreso" in agent_cols and not _index_exists(connection, "agentes_operativos", "ix_agentes_operativos_qr_impreso"):
            connection.execute(
                text("CREATE INDEX `ix_agentes_operativos_qr_impreso` ON `agentes_operativos` (`qr_impreso`)")
            )

        if not _index_exists(connection, "pagos_semanales", "ix_pagos_semanales_agente_semana_pagado"):
            connection.execute(
                text(
                    "CREATE INDEX `ix_pagos_semanales_agente_semana_pagado` ON `pagos_semanales` (`agente_id`, `semana_inicio`, `pagado`)"
                )
            )

        if not _index_exists(connection, "pagos_semanales", "ix_pagos_semanales_fecha_pago_monto"):
            connection.execute(
                text(
                    "CREATE INDEX `ix_pagos_semanales_fecha_pago_monto` ON `pagos_semanales` (`fecha_pago`, `monto`)"
                )
            )

        if not _index_exists(connection, "pagos_semanales", "ix_pagos_semanales_semana_monto"):
            connection.execute(
                text(
                    "CREATE INDEX `ix_pagos_semanales_semana_monto` ON `pagos_semanales` (`semana_inicio`, `monto`)"
                )
            )

        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS `cat_estatus_agente` (
                    `codigo` VARCHAR(20) NOT NULL,
                    `nombre` VARCHAR(80) NOT NULL,
                    `descripcion` VARCHAR(255) NULL,
                    `es_operativo` TINYINT(1) NOT NULL DEFAULT 1,
                    `orden` INT NOT NULL DEFAULT 100,
                    PRIMARY KEY (`codigo`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO `cat_estatus_agente` (`codigo`, `nombre`, `descripcion`, `es_operativo`, `orden`)
                VALUES
                    ('ACTIVO', 'Activo', 'Agente operativo vigente', 1, 10),
                    ('SUSPENDIDO', 'Suspendido', 'Bloqueado temporalmente', 0, 20),
                    ('BAJA', 'Baja', 'Agente dado de baja', 0, 30)
                ON DUPLICATE KEY UPDATE
                    `nombre` = VALUES(`nombre`),
                    `descripcion` = VALUES(`descripcion`),
                    `es_operativo` = VALUES(`es_operativo`),
                    `orden` = VALUES(`orden`)
                """
            )
        )

        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS `agente_eventos_operativos` (
                    `id` BIGINT NOT NULL AUTO_INCREMENT,
                    `agente_id` INT NOT NULL,
                    `usuario_id` INT NULL,
                    `evento` VARCHAR(40) NOT NULL,
                    `detalle` TEXT NULL,
                    `payload_json` JSON NULL,
                    `fecha_evento` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (`id`),
                    KEY `ix_agente_eventos_operativos_agente_fecha` (`agente_id`, `fecha_evento`),
                    KEY `ix_agente_eventos_operativos_evento_fecha` (`evento`, `fecha_evento`),
                    CONSTRAINT `fk_agente_eventos_operativos_agente`
                        FOREIGN KEY (`agente_id`) REFERENCES `agentes_operativos` (`id`)
                        ON DELETE CASCADE,
                    CONSTRAINT `fk_agente_eventos_operativos_usuario`
                        FOREIGN KEY (`usuario_id`) REFERENCES `usuarios` (`id`)
                        ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
        )

        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS `cobros_movimientos` (
                    `id` BIGINT NOT NULL AUTO_INCREMENT,
                    `agente_id` INT NOT NULL,
                    `semana_inicio` DATE NULL,
                    `tipo_movimiento` VARCHAR(30) NOT NULL,
                    `monto` DECIMAL(12,2) NOT NULL DEFAULT 0,
                    `referencia_pago_id` INT NULL,
                    `usuario_id` INT NULL,
                    `payload_json` JSON NULL,
                    `creado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (`id`),
                    KEY `ix_cobros_movimientos_agente_semana` (`agente_id`, `semana_inicio`),
                    KEY `ix_cobros_movimientos_tipo_fecha` (`tipo_movimiento`, `creado_en`),
                    CONSTRAINT `fk_cobros_movimientos_agente`
                        FOREIGN KEY (`agente_id`) REFERENCES `agentes_operativos` (`id`)
                        ON DELETE CASCADE,
                    CONSTRAINT `fk_cobros_movimientos_pago`
                        FOREIGN KEY (`referencia_pago_id`) REFERENCES `pagos_semanales` (`id`)
                        ON DELETE SET NULL,
                    CONSTRAINT `fk_cobros_movimientos_usuario`
                        FOREIGN KEY (`usuario_id`) REFERENCES `usuarios` (`id`)
                        ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
        )

        connection.execute(
            text(
                """
                UPDATE usuarios
                SET rol = CASE
                    WHEN COALESCE(es_admin, 0) = 1 THEN :admin_role
                    WHEN rol IS NULL OR rol = '' THEN :viewer_role
                    ELSE LOWER(rol)
                END
                """
            ),
            {"admin_role": ROLE_ADMIN, "viewer_role": ROLE_VIEWER},
        )

        for _name, _sql in get_useful_views_sql_map(connection).items():
            connection.execute(text(_sql))

        _execute_optional(
            connection,
            """
            CREATE OR REPLACE VIEW vw_control_sync_agentes AS
            SELECT
                d.id AS agente_id,
                d.nombre AS nombre_operativo,
                JSON_UNQUOTE(JSON_EXTRACT(d.datos_adicionales, '$.alias')) AS alias_operativo,
                a.Nombre AS nombre_legacy,
                a.alias AS alias_legacy,
                CASE
                    WHEN a.ID IS NULL THEN 'FALTANTE_EN_LEGACY'
                    WHEN COALESCE(a.Nombre, '') <> COALESCE(d.nombre, '')
                        OR COALESCE(a.alias, '') <> COALESCE(JSON_UNQUOTE(JSON_EXTRACT(d.datos_adicionales, '$.alias')), '')
                    THEN 'DESALINEADO'
                    ELSE 'EN_SYNC'
                END AS estado_sync
            FROM agentes_operativos d
            LEFT JOIN registro_agentes.agentes a ON a.ID = d.id
            WHERE COALESCE(d.es_activo, 1) = 1
            """,
            label="vw_control_sync_agentes",
        )

        current_db = _safe_identifier(config.DB_NAME, "database_manager")
        legacy_db = _safe_identifier(config.PBX_DB_NAME, "registro_agentes")

        _execute_optional(
            connection,
            f"""
            CREATE OR REPLACE VIEW `{legacy_db}`.`vw_dm_agentes_operacion_actual` AS
            SELECT * FROM `{current_db}`.`vw_agentes_operacion_actual`
            """,
            label="registro_agentes.vw_dm_agentes_operacion_actual",
        )

        _execute_optional(
            connection,
            f"""
            CREATE OR REPLACE VIEW `{legacy_db}`.`vw_dm_control_sync_agentes` AS
            SELECT * FROM `{current_db}`.`vw_control_sync_agentes`
            """,
            label="registro_agentes.vw_dm_control_sync_agentes",
        )

        _execute_optional(
            connection,
            f"""
            CREATE OR REPLACE VIEW `{legacy_db}`.`vw_dm_cat_estatus_agente` AS
            SELECT * FROM `{current_db}`.`cat_estatus_agente`
            """,
            label="registro_agentes.vw_dm_cat_estatus_agente",
        )


def get_db() -> Session:
    """Dependency para obtener sesión de BD."""
    db = SessionLocal()
    try:
        # Reset database context in case a previous request switched via USE.
        db.execute(text(f"USE `{config.DB_NAME}`"))
        yield db
    finally:
        db.close()


class RepositorioBase:
    """Clase base para repositorios (CRUD genérico)."""
    
    def __init__(self, model, db: Session):
        self.model = model
        self.db = db
    
    def crear(self, obj_in):
        """Crear nuevo registro."""
        payload = obj_in.model_dump() if hasattr(obj_in, "model_dump") else obj_in.dict()
        db_obj = self.model(**payload)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        logger.info(f"Creado {self.model.__name__}: {db_obj}")
        return db_obj
    
    def obtener_por_id(self, id: int):
        """Obtener por ID."""
        return self.db.query(self.model).filter(self.model.id == id).first()
    
    def obtener_todos(self, skip: int = 0, limit: int = 100):
        """Obtener todos (con paginación)."""
        return self.db.query(self.model).offset(skip).limit(limit).all()
    
    def actualizar(self, id: int, obj_in):
        """Actualizar registro."""
        db_obj = self.obtener_por_id(id)
        if not db_obj:
            return None
        
        update_data = obj_in.model_dump(exclude_unset=True) if hasattr(obj_in, "model_dump") else obj_in.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        logger.info(f"Actualizado {self.model.__name__}: {db_obj}")
        return db_obj
    
    def eliminar(self, id: int):
        """Eliminar (soft delete)."""
        db_obj = self.obtener_por_id(id)
        if not db_obj:
            return False
        
        if hasattr(db_obj, 'es_activo'):
            db_obj.es_activo = False
        if hasattr(db_obj, 'fecha_eliminacion'):
            from datetime import datetime
            db_obj.fecha_eliminacion = datetime.utcnow()
        
        self.db.add(db_obj)
        self.db.commit()
        logger.info(f"Eliminado {self.model.__name__}: {db_obj}")
        return True
