"""Base de datos mejorada usando SQLAlchemy ORM."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import logging
from app.config import config
from app.models import Base

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
        logger.info("Tablas de base de datos creadas/verificadas")
    except Exception as e:
        logger.error(f"Error creando tablas: {e}")
        raise


def get_db() -> Session:
    """Dependency para obtener sesión de BD."""
    db = SessionLocal()
    try:
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
