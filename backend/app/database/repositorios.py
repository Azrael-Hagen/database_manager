"""Repositorios específicos para modelos."""

from sqlalchemy.orm import Session
from app.models import Usuario, DatoImportado, ImportLog, AuditoriaAccion
from app.schemas import UsuarioCrear, DatoImportadoCrear, DatoImportadoActualizar
from app.security import hash_password, verify_password
from app.database.orm import RepositorioBase
from datetime import datetime
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


class RepositorioUsuario(RepositorioBase):
    """Repositorio para usuarios."""
    
    def __init__(self, db: Session):
        super().__init__(Usuario, db)
    
    def obtener_todos(self, skip: int = 0, limit: int = 100) -> List[Usuario]:
        """Obtener todos los usuarios."""
        return self.db.query(Usuario).offset(skip).limit(limit).all()
    
    def obtener_por_username(self, username: str) -> Optional[Usuario]:
        """Obtener usuario por nombre de usuario."""
        return self.db.query(Usuario).filter(Usuario.username == username).first()
    
    def obtener_por_email(self, email: str) -> Optional[Usuario]:
        """Obtener usuario por email."""
        return self.db.query(Usuario).filter(Usuario.email == email).first()
    
    def crear_usuario(self, usuario_dict: dict) -> Usuario:
        """Crear nuevo usuario desde dict."""
        usuario = Usuario(**usuario_dict)
        self.db.add(usuario)
        self.db.commit()
        self.db.refresh(usuario)
        logger.info(f"Usuario creado: {usuario.username}")
        return usuario
    
    def actualizar_usuario(self, usuario_id: int, updates: dict) -> Usuario:
        """Actualizar usuario."""
        usuario = self.obtener_por_id(usuario_id)
        if usuario:
            for key, value in updates.items():
                if hasattr(usuario, key):
                    setattr(usuario, key, value)
            self.db.add(usuario)
            self.db.commit()
            self.db.refresh(usuario)
        return usuario
    
    def eliminar_usuario(self, usuario_id: int):
        """Eliminar usuario (soft delete)."""
        usuario = self.obtener_por_id(usuario_id)
        if usuario:
            usuario.es_activo = False
            self.db.add(usuario)
            self.db.commit()
            logger.info(f"Usuario eliminado: {usuario.username}")
    
    def actualizar_password(self, usuario_id: int, nueva_password_hash: str):
        """Actualizar contraseña."""
        usuario = self.obtener_por_id(usuario_id)
        if usuario:
            usuario.hashed_password = nueva_password_hash
            self.db.add(usuario)
            self.db.commit()
            logger.info(f"Contraseña actualizada para: {usuario.username}")
    
    def crear(self, usuario_in: UsuarioCrear) -> Usuario:
        """Crear nuevo usuario (método legacy)."""
        usuario_dict = usuario_in.dict()
        password = usuario_dict.pop("password")
        usuario_dict["hashed_password"] = hash_password(password)
        
        usuario = Usuario(**usuario_dict)
        self.db.add(usuario)
        self.db.commit()
        self.db.refresh(usuario)
        logger.info(f"Usuario creado: {usuario.username}")
        return usuario
    
    def autenticar(self, username: str, password: str) -> Optional[Usuario]:
        """Autenticar usuario."""
        usuario = self.obtener_por_username(username)
        if not usuario or not verify_password(password, usuario.hashed_password):
            return None
        return usuario
    
    def actualizar_ultima_sesion(self, usuario_id: int):
        """Actualizar fecha de última sesión."""
        usuario = self.obtener_por_id(usuario_id)
        if usuario:
            usuario.fecha_ultima_sesion = datetime.utcnow()
            self.db.add(usuario)
            self.db.commit()


class RepositorioDatoImportado(RepositorioBase):
    """Repositorio para datos importados."""
    
    def __init__(self, db: Session):
        super().__init__(DatoImportado, db)
    
    def crear_lote(self, datos_lista: List[dict], usuario_id: int, importacion_id: int) -> List[DatoImportado]:
        """Crear múltiples datos (batch insert)."""
        registros = []
        for datos in datos_lista:
            datos['creado_por'] = usuario_id
            datos['importacion_id'] = importacion_id
            registro = DatoImportado(**datos)
            registros.append(registro)
        
        self.db.add_all(registros)
        self.db.commit()
        logger.info(f"Creados {len(registros)} registros en lote")
        return registros
    
    def obtener_por_uuid(self, uuid: str) -> Optional[DatoImportado]:
        """Obtener por UUID."""
        return self.db.query(DatoImportado).filter(DatoImportado.uuid == uuid).first()
    
    def buscar(self, tabla: str = None, buscar: str = None, filtros: dict = None, 
               skip: int = 0, limit: int = 100) -> tuple:
        """Buscar registros con filtros."""
        query = self.db.query(DatoImportado).filter(DatoImportado.es_activo == True)
        
        if buscar:
            query = query.filter(
                (DatoImportado.nombre.ilike(f"%{buscar}%")) |
                (DatoImportado.email.ilike(f"%{buscar}%")) |
                (DatoImportado.empresa.ilike(f"%{buscar}%"))
            )
        
        if filtros:
            for key, value in filtros.items():
                if hasattr(DatoImportado, key):
                    query = query.filter(getattr(DatoImportado, key) == value)
        
        total = query.count()
        registros = query.offset(skip).limit(limit).all()
        
        return registros, total
    
    def obtener_por_importacion(self, importacion_id: int) -> List[DatoImportado]:
        """Obtener todos los datos de una importación."""
        return self.db.query(DatoImportado).filter(
            DatoImportado.importacion_id == importacion_id,
            DatoImportado.es_activo == True
        ).all()


class RepositorioImportLog(RepositorioBase):
    """Repositorio para logs de importación."""
    
    def __init__(self, db: Session):
        super().__init__(ImportLog, db)
    
    def obtener_por_usuario(self, usuario_id: int, skip: int = 0, limit: int = 100) -> List[ImportLog]:
        """Obtener importaciones de un usuario."""
        return self.db.query(ImportLog).filter(
            ImportLog.usuario_id == usuario_id
        ).order_by(ImportLog.fecha_inicio.desc()).offset(skip).limit(limit).all()
    
    def obtener_por_uuid(self, uuid: str) -> Optional[ImportLog]:
        """Obtener por UUID."""
        return self.db.query(ImportLog).filter(ImportLog.uuid == uuid).first()
    
    def actualizar_completado(self, importacion_id: int, registros_importados: int,
                             registros_fallidos: int, estado: str, duracion: int,
                             mensaje_error: str = None):
        """Actualizar importación como completada."""
        importacion = self.obtener_por_id(importacion_id)
        if importacion:
            importacion.registros_importados = registros_importados
            importacion.registros_fallidos = registros_fallidos
            importacion.estado = estado
            importacion.duracion_segundos = duracion
            importacion.fecha_fin = datetime.utcnow()
            importacion.mensaje_error = mensaje_error
            
            self.db.add(importacion)
            self.db.commit()
            logger.info(f"Actualizado log de importación {importacion_id}: {estado}")


class RepositorioAuditoria(RepositorioBase):
    """Repositorio para auditoría."""
    
    def __init__(self, db: Session):
        super().__init__(AuditoriaAccion, db)
    
    def registrar_accion(self, usuario_id: int, tipo_accion: str, tabla: str,
                        registro_id: int = None, descripcion: str = None,
                        datos_anteriores: str = None, datos_nuevos: str = None,
                        resultado: str = "SUCCESS", ip_origen: str = None,
                        user_agent: str = None):
        """Registrar acción en auditoría."""
        accion = AuditoriaAccion(
            usuario_id=usuario_id,
            tipo_accion=tipo_accion,
            tabla=tabla,
            registro_id=registro_id,
            descripcion=descripcion,
            datos_anteriores=datos_anteriores,
            datos_nuevos=datos_nuevos,
            resultado=resultado,
            ip_origen=ip_origen,
            user_agent=user_agent
        )
        self.db.add(accion)
        self.db.commit()
        logger.info(f"Auditoría: {tipo_accion} en {tabla}")
