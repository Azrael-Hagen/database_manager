"""Repositorios específicos para modelos."""

from sqlalchemy import text
from sqlalchemy.orm import Session
from app.models import (
    AgenteLadaPreferencia,
    AgenteLineaAsignacion,
    AlertaPago,
    AuditoriaAccion,
    DatoImportado,
    EsquemaBaseDatos,
    ImportLog,
    PagoSemanal,
    Usuario,
)
from app.schemas import UsuarioCrear, DatoImportadoCrear, DatoImportadoActualizar
from app.security import ROLE_ADMIN, normalize_role, hash_password, verify_password
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
        role = normalize_role(usuario_dict.get("rol"), bool(usuario_dict.get("es_admin")))
        usuario_dict["rol"] = role
        usuario_dict["es_admin"] = role == ROLE_ADMIN
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
            if "rol" in updates or "es_admin" in updates:
                role = normalize_role(updates.get("rol", usuario.rol), bool(updates.get("es_admin", usuario.es_admin)))
                updates["rol"] = role
                updates["es_admin"] = role == ROLE_ADMIN
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
        role = normalize_role(usuario_dict.get("rol"), bool(usuario_dict.get("es_admin")))
        usuario_dict["rol"] = role
        usuario_dict["es_admin"] = role == ROLE_ADMIN
        
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

    def eliminar_usuario_definitivo(self, usuario_id: int, reassigned_user_id: int | None = None) -> bool:
        """Eliminar usuario y resolver dependencias persistentes."""
        usuario = self.obtener_por_id(usuario_id)
        if not usuario:
            return False

        self.db.query(AuditoriaAccion).filter(AuditoriaAccion.usuario_id == usuario_id).delete(synchronize_session=False)
        self.db.query(DatoImportado).filter(DatoImportado.creado_por == usuario_id).update(
            {DatoImportado.creado_por: None}, synchronize_session=False
        )
        self.db.query(EsquemaBaseDatos).filter(EsquemaBaseDatos.guardar_por == usuario_id).update(
            {EsquemaBaseDatos.guardar_por: None}, synchronize_session=False
        )
        if reassigned_user_id:
            self.db.query(ImportLog).filter(ImportLog.usuario_id == usuario_id).update(
                {ImportLog.usuario_id: reassigned_user_id}, synchronize_session=False
            )
        else:
            logs = self.db.query(ImportLog).filter(ImportLog.usuario_id == usuario_id).all()
            for log in logs:
                if log.datos:
                    raise ValueError("El usuario tiene importaciones con datos asociados; reasigna primero el propietario")
                self.db.delete(log)

        self.db.delete(usuario)
        self.db.commit()
        logger.info(f"Usuario eliminado definitivamente: {usuario.username}")
        return True


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

    def eliminar_definitivo(self, dato_id: int) -> bool:
        """Eliminar definitivamente un dato y sus dependencias operativas."""
        dato = self.obtener_por_id(dato_id)
        if not dato:
            return False

        self.db.query(PagoSemanal).filter(PagoSemanal.agente_id == dato_id).delete(synchronize_session=False)
        self.db.query(AlertaPago).filter(AlertaPago.agente_id == dato_id).delete(synchronize_session=False)
        self.db.query(AgenteLineaAsignacion).filter(AgenteLineaAsignacion.agente_id == dato_id).delete(synchronize_session=False)
        self.db.query(AgenteLadaPreferencia).filter(AgenteLadaPreferencia.agente_id == dato_id).delete(synchronize_session=False)
        self.db.delete(dato)
        self.db.commit()
        logger.info(f"Dato eliminado definitivamente: {dato_id}")
        return True

    def purgar_inactivos(self) -> int:
        """Eliminar definitivamente registros marcados como inactivos."""
        ids = [row[0] for row in self.db.query(DatoImportado.id).filter(DatoImportado.es_activo.is_(False)).all()]
        deleted = 0
        for dato_id in ids:
            if self.eliminar_definitivo(dato_id):
                deleted += 1
        return deleted


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
