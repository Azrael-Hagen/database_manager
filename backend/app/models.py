"""Modelos de base de datos con SQLAlchemy ORM."""

from sqlalchemy import Column, Integer, String, DateTime, LargeBinary, Boolean, Text, ForeignKey, Date, Float
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import uuid

Base = declarative_base()


class Usuario(Base):
    """Modelo de usuario con autenticación."""
    
    __tablename__ = "usuarios"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    nombre_completo = Column(String(255))
    es_activo = Column(Boolean, default=True)
    es_admin = Column(Boolean, default=False)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    fecha_ultima_sesion = Column(DateTime)
    
    # Relaciones
    importaciones = relationship("ImportLog", back_populates="usuario")
    registros_creados = relationship("DatoImportado", back_populates="creado_por_usuario")
    
    def __repr__(self):
        return f"<Usuario {self.username}>"


class DatoImportado(Base):
    """Modelo para datos importados con auditoría."""
    
    __tablename__ = "datos_importados"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, default=lambda: str(uuid.uuid4()))
    nombre = Column(String(255), index=True)
    email = Column(String(255), index=True)
    telefono = Column(String(20))
    empresa = Column(String(255), index=True)
    ciudad = Column(String(100))
    pais = Column(String(100))
    datos_adicionales = Column(Text)  # JSON flexible para campos custom
    
    # QR
    qr_code = Column(LargeBinary)
    qr_filename = Column(String(255))
    contenido_qr = Column(Text)  # Serializado en JSON
    
    # Auditoría
    creado_por = Column(Integer, ForeignKey("usuarios.id"))
    creado_por_usuario = relationship("Usuario", back_populates="registros_creados")
    fecha_creacion = Column(DateTime, default=datetime.utcnow, index=True)
    fecha_modificacion = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    fecha_eliminacion = Column(DateTime)  # Para soft delete
    es_activo = Column(Boolean, default=True, index=True)
    
    # Rastreo
    importacion_id = Column(Integer, ForeignKey("import_logs.id"))
    importacion = relationship("ImportLog", back_populates="datos")
    
    def __repr__(self):
        return f"<DatoImportado {self.nombre}>"


class PagoSemanal(Base):
    """Pago semanal por agente/número."""

    __tablename__ = "pagos_semanales"

    id = Column(Integer, primary_key=True, index=True)
    agente_id = Column(Integer, ForeignKey("datos_importados.id"), nullable=False, index=True)
    telefono = Column(String(20), nullable=False, index=True)
    numero_voip = Column(String(50), nullable=True, index=True)
    semana_inicio = Column(Date, nullable=False, index=True)
    monto = Column(Float, default=0.0)
    pagado = Column(Boolean, default=False, index=True)
    fecha_pago = Column(DateTime)
    observaciones = Column(Text)
    fecha_creacion = Column(DateTime, default=datetime.utcnow, index=True)
    fecha_actualizacion = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    agente = relationship("DatoImportado")

    def __repr__(self):
        return f"<PagoSemanal agente={self.agente_id} semana={self.semana_inicio} pagado={self.pagado}>"


class ImportLog(Base):
    """Log de importaciones con auditoría completa."""
    
    __tablename__ = "import_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, default=lambda: str(uuid.uuid4()))
    
    # Información de importación
    archivo_nombre = Column(String(255), nullable=False)
    archivo_tamanio = Column(Integer)  # En bytes
    tipo_archivo = Column(String(20), nullable=False)  # CSV, EXCEL, TXT, DAT
    tabla_destino = Column(String(255), nullable=False, index=True)
    delimitador = Column(String(10))
    
    # Resultados
    registros_totales = Column(Integer, default=0)
    registros_importados = Column(Integer, default=0)
    registros_fallidos = Column(Integer, default=0)
    estado = Column(String(20), nullable=False)  # SUCCESS, FAILED, PARTIAL, PENDING
    mensaje_error = Column(Text)
    
    # Usuario y auditoría
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    usuario = relationship("Usuario", back_populates="importaciones")
    fecha_inicio = Column(DateTime, default=datetime.utcnow)
    fecha_fin = Column(DateTime)
    duracion_segundos = Column(Integer)
    
    # Relación con datos
    datos = relationship("DatoImportado", back_populates="importacion", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ImportLog {self.archivo_nombre}>"


class AuditoriaAccion(Base):
    """Auditoría de todas las acciones en el sistema."""
    
    __tablename__ = "auditoria_acciones"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Usuario y acción
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    usuario = relationship("Usuario")
    tipos_accion = ["CREAR", "LEER", "ACTUALIZAR", "ELIMINAR", "IMPORTAR", "EXPORTAR", "LOGIN", "LOGOUT"]
    tipo_accion = Column(String(20), nullable=False, index=True)
    
    # Entidad afectada
    tabla = Column(String(50), nullable=False, index=True)
    registro_id = Column(Integer, index=True)
    
    # Detalles
    descripcion = Column(Text)
    datos_anteriores = Column(Text)  # JSON
    datos_nuevos = Column(Text)  # JSON
    resultado = Column(String(20))  # SUCCESS, FAILED
    ip_origen = Column(String(45))  # IPv4 o IPv6
    user_agent = Column(String(255))
    
    fecha = Column(DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f"<AuditoriaAccion {self.tipo_accion}>"
