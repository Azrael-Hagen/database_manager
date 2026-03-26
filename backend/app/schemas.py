"""Esquemas Pydantic para validación de datos."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
from datetime import datetime
from typing import Optional, Dict, Any, List
import json
import re
from datetime import date


class UsuarioBase(BaseModel):
    """Esquema base de usuario."""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    nombre_completo: Optional[str] = Field(None, max_length=255)
    rol: str = Field("viewer", pattern="^(viewer|capture|admin|super_admin)$")


class UsuarioCrear(UsuarioBase):
    """Esquema para crear usuario."""
    password: str = Field(..., min_length=8, max_length=100)
    es_admin: bool = False
    es_activo: bool = True

    @model_validator(mode='after')
    def normalize_role_for_create(self):
        role = str(self.rol or "").strip().lower()
        if not role:
            role = "admin" if self.es_admin else "viewer"
        if role not in {"viewer", "capture", "admin", "super_admin"}:
            raise ValueError('Rol inválido')
        self.rol = role
        return self

    @field_validator('password')
    @classmethod
    def password_strength(cls, v):
        """Validar fortaleza de contraseña."""
        if not re.search(r'[A-Z]', v):
            raise ValueError('Contraseña debe contener mayúscula')
        if not re.search(r'[0-9]', v):
            raise ValueError('Contraseña debe contener número')
        if not re.search(r'[!@#$%^&*]', v):
            raise ValueError('Contraseña debe contener carácter especial')
        return v


class UsuarioActualizar(BaseModel):
    """Esquema para actualizar usuario."""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    nombre_completo: Optional[str] = Field(None, max_length=255)
    es_activo: Optional[bool] = None
    es_admin: Optional[bool] = None
    rol: Optional[str] = Field(None, pattern="^(viewer|capture|admin|super_admin)$")

    @field_validator('rol')
    @classmethod
    def normalize_role_for_update(cls, value):
        if value is None:
            return value
        role = str(value).strip().lower()
        if role not in {"viewer", "capture", "admin", "super_admin"}:
            raise ValueError('Rol inválido')
        return role


class Usuario(UsuarioBase):
    """Esquema completo de usuario para respuestas."""
    id: int
    es_activo: bool = True
    es_admin: bool = False
    es_temporal: bool = False
    temporal_expira_en: Optional[datetime] = None
    temporal_renovaciones: int = 0
    solicitud_permiso_estado: Optional[str] = None
    solicitud_permiso_rol: Optional[str] = None
    solicitud_permiso_motivo: Optional[str] = None
    solicitud_permiso_fecha: Optional[datetime] = None
    fecha_creacion: datetime
    fecha_actualizacion: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UsuarioAuth(BaseModel):
    """Esquema para autenticación."""
    username: str
    password: str


class UsuarioTemporalCrear(BaseModel):
    """Crear usuario temporal con vigencia controlada."""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    nombre_completo: Optional[str] = Field(None, max_length=255)
    dias_vigencia: int = Field(10, ge=1, le=10)

    @field_validator('password')
    @classmethod
    def password_strength(cls, v):
        if not re.search(r'[A-Z]', v):
            raise ValueError('Contraseña debe contener mayúscula')
        if not re.search(r'[0-9]', v):
            raise ValueError('Contraseña debe contener número')
        if not re.search(r'[!@#$%^&*]', v):
            raise ValueError('Contraseña debe contener carácter especial')
        return v


class UsuarioTemporalRenovar(BaseModel):
    """Renovar vigencia de un usuario temporal."""
    dias_vigencia: int = Field(10, ge=1, le=10)


class SolicitudPermisoCrear(BaseModel):
    """Solicitud de escalamiento de permisos para usuarios temporales."""
    rol_solicitado: str = Field("viewer", pattern="^(viewer|capture|admin)$")
    motivo: Optional[str] = Field(None, max_length=500)


class SolicitudPermisoResolver(BaseModel):
    """Resolver solicitud de escalamiento."""
    aprobar: bool = True
    rol_aprobado: str = Field("viewer", pattern="^(viewer|capture|admin)$")


class TempUsuarioHistorialItem(BaseModel):
    """Registro histórico de usuario temporal eliminado."""
    id: int
    usuario_id: int
    username: str
    email: Optional[str] = None
    rol: str
    fecha_creacion_usuario: Optional[datetime] = None
    fecha_expiracion: Optional[datetime] = None
    fecha_eliminacion: datetime
    motivo: str
    eliminado_por: Optional[int] = None
    detalle_json: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PasswordUpdate(BaseModel):
    """Esquema para actualizar contraseña."""
    password: str = Field(..., min_length=8, max_length=100)

    @field_validator('password')
    @classmethod
    def password_strength(cls, v):
        """Validar fortaleza de contraseña."""
        if not re.search(r'[A-Z]', v):
            raise ValueError('Contraseña debe contener mayúscula')
        if not re.search(r'[0-9]', v):
            raise ValueError('Contraseña debe contener número')
        if not re.search(r'[!@#$%^&*]', v):
            raise ValueError('Contraseña debe contener carácter especial')
        return v


class Token(BaseModel):
    """Esquema de token JWT."""
    access_token: str
    token_type: str
    usuario: Usuario


class DatoImportadoBase(BaseModel):
    """Esquema base de dato importado."""
    nombre: str = Field(..., min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    telefono: Optional[str] = Field(None, max_length=20)
    empresa: Optional[str] = Field(None, max_length=255)
    ciudad: Optional[str] = Field(None, max_length=100)
    pais: Optional[str] = Field(None, max_length=100)
    datos_adicionales: Optional[Dict[str, Any]] = None

    @field_validator('datos_adicionales', mode='before')
    @classmethod
    def parse_datos_adicionales(cls, v):
        """Acepta tanto dict como JSON-string para datos_adicionales."""
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
        return v

    @field_validator('telefono')
    @classmethod
    def validate_telefono(cls, v):
        """Validar formato de teléfono."""
        if v and not re.match(r'^[\d\-\+\s\(\)]{7,}$', v):
            raise ValueError('Formato de teléfono inválido')
        return v


class DatoImportadoCrear(DatoImportadoBase):
    """Esquema para crear dato."""
    pass


class DatoImportadoActualizar(BaseModel):
    """Esquema para actualizar dato."""
    nombre: Optional[str] = None
    email: Optional[EmailStr] = None
    telefono: Optional[str] = None
    empresa: Optional[str] = None
    ciudad: Optional[str] = None
    pais: Optional[str] = None
    es_activo: Optional[bool] = None
    datos_adicionales: Optional[Dict[str, Any]] = None


class DatoImportado(DatoImportadoBase):
    """Esquema de dato importado (lectura)."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    uuid: str
    qr_filename: Optional[str]
    fecha_creacion: datetime
    fecha_modificacion: datetime


class ImportLogBase(BaseModel):
    """Esquema base de log de importación."""
    archivo_nombre: str
    tabla_destino: str
    tipo_archivo: str = Field(..., pattern="^(CSV|EXCEL|TXT|DAT)$")
    delimitador: Optional[str] = None


class ImportLogCrear(ImportLogBase):
    """Esquema para crear log de importación."""
    pass


class ImportLog(ImportLogBase):
    """Esquema de log de importación (lectura)."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    uuid: str
    registros_totales: int
    registros_importados: int
    registros_fallidos: int
    estado: str
    fecha_inicio: datetime
    fecha_fin: Optional[datetime]
    duracion_segundos: Optional[int]
    datos: List[DatoImportado] = []


class BusquedaParametros(BaseModel):
    """Parámetros de búsqueda y paginación."""
    pagina: int = Field(1, ge=1)
    por_pagina: int = Field(10, ge=1, le=100)
    ordenar_por: Optional[str] = "fecha_creacion"
    direccion: Optional[str] = "desc"  # asc o desc
    buscar: Optional[str] = None
    filtro: Optional[Dict[str, Any]] = None


class RespuestaExitosa(BaseModel):
    """Respuesta exitosa genérica."""
    status: str = "success"
    mensaje: str
    data: Optional[Dict[str, Any]] = None


class RespuestaError(BaseModel):
    """Respuesta de error genérica."""
    status: str = "error"
    mensaje: str
    detalles: Optional[str] = None


class RespuestaPaginada(BaseModel):
    """Respuesta paginada genérica."""
    status: str = "success"
    data: List[Any]
    pagina: int
    por_pagina: int
    total: int
    total_paginas: int


class PagoSemanalCrear(BaseModel):
    """Registrar pago semanal de un agente."""
    agente_id: int
    telefono: Optional[str] = Field(None, max_length=20)
    numero_voip: Optional[str] = Field(None, max_length=50)
    semana_inicio: date
    monto: float = Field(0.0, ge=0)
    pagado: bool = True
    observaciones: Optional[str] = Field(None, max_length=500)
    liquidar_total: bool = False


class PagoSemanalAdminActualizar(BaseModel):
    """Edicion administrativa de pago semanal existente."""
    monto: Optional[float] = Field(None, ge=0)
    pagado: Optional[bool] = None
    observaciones: Optional[str] = Field(None, max_length=500)


class PagoSemanalRevertir(BaseModel):
    """Solicitud de reversa administrativa de pago semanal."""
    motivo: Optional[str] = Field(None, max_length=500)


class PagoSemanalRespuesta(BaseModel):
    """Respuesta de pago semanal."""
    id: int
    agente_id: int
    telefono: str
    numero_voip: Optional[str] = None
    semana_inicio: date
    monto: float
    pagado: bool
    fecha_pago: Optional[datetime] = None
    observaciones: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
