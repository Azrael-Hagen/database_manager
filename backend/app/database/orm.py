"""Base de datos mejorada usando SQLAlchemy ORM."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import logging
from app.config import config
from app.models import Base
from app.security import ROLE_ADMIN, ROLE_VIEWER

logger = logging.getLogger(__name__)

# Configurar engine
engine = create_engine(
    config.DATABASE_URL,
    echo=config.API_DEBUG,
    pool_pre_ping=True,  # Verificar conexión antes de usar
    pool_recycle=3600,   # Reciclar conexiones cada hora
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


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
        role_column_exists = connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE table_schema = DATABASE()
                  AND table_name = 'usuarios'
                  AND column_name = 'rol'
                """
            )
        ).scalar()
        if not role_column_exists:
            connection.execute(text("ALTER TABLE `usuarios` ADD COLUMN `rol` VARCHAR(20) NOT NULL DEFAULT 'viewer'"))
            connection.execute(text("CREATE INDEX `ix_usuarios_rol` ON `usuarios` (`rol`)"))

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

        connection.execute(
            text(
                """
                CREATE OR REPLACE VIEW vw_agentes_qr_estado AS
                SELECT
                    id,
                    uuid,
                    nombre,
                    telefono,
                    COALESCE(es_activo, 1) AS es_activo,
                    CASE WHEN qr_filename IS NOT NULL AND qr_filename <> '' THEN 1 ELSE 0 END AS tiene_qr,
                    fecha_creacion
                FROM datos_importados
                """
            )
        )
        connection.execute(
            text(
                """
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
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE OR REPLACE VIEW vw_agentes_extensiones_pago_actual AS
                SELECT
                    d.id AS agente_id,
                    d.uuid,
                    d.nombre,
                    COALESCE(d.es_activo, 1) AS es_activo,
                    l.id AS linea_id,
                    l.numero AS extension_numero,
                    l.tipo AS extension_tipo,
                    p.semana_inicio,
                    COALESCE(p.pagado, 0) AS pagado_semana,
                    COALESCE(p.monto, 0) AS monto_semana,
                    p.fecha_pago,
                    CASE
                        WHEN p.id IS NULL OR COALESCE(p.pagado, 0) = 0 THEN 'DEBE'
                        ELSE 'PAGADO'
                    END AS estado_pago
                FROM datos_importados d
                LEFT JOIN agente_linea_asignaciones ala
                    ON ala.agente_id = d.id AND ala.es_activa = 1
                LEFT JOIN lineas_telefonicas l
                    ON l.id = ala.linea_id AND COALESCE(l.es_activa, 1) = 1
                LEFT JOIN pagos_semanales p
                    ON p.agente_id = d.id
                   AND p.semana_inicio = DATE_SUB(CURDATE(), INTERVAL WEEKDAY(CURDATE()) DAY)
                WHERE COALESCE(d.es_activo, 1) = 1
                """
            )
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
        db_obj = self.model(**obj_in.dict())
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
        
        update_data = obj_in.dict(exclude_unset=True)
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
