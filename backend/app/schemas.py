"""Esquemas Pydantic para validación de datos."""

from pydantic import BaseModel, EmailStr, Field, validator
from datetime import datetime
from typing import Optional, Dict, Any, List
import re


class UsuarioBase(BaseModel):
    """Esquema base de usuario."""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    nombre_completo: Optional[str] = Field(None, max_length=255)


class UsuarioCrear(UsuarioBase):
    """Esquema para crear usuario."""
    password: str = Field(..., min_length=8, max_length=100)
    
    @validator('password')
    def password_strength(cls, v):
        """Validar fortaleza de contraseña."""
        if not re.search(r'[A-Z]', v):
            raise ValueError('Contraseña debe contener mayúscula')
        if not re.search(r'[0-9]', v):
            raise ValueError('Contraseña debe contener número')
        if not re.search(r'[!@#$%^&*]', v):
            raise ValueError('Contraseña debe contener carácter especial')
        return v


class Usuario(UsuarioBase):
    """Esquema de usuario (lectura)."""
    
    class Config:
        from_attributes = True
    
    id: int
    es_activo: bool
    fecha_creacion: datetime


class UsuarioAuth(BaseModel):
    """Esquema para autenticación."""
    username: str
    password: str


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
    
    @validator('telefono')
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
    datos_adicionales: Optional[Dict[str, Any]] = None


class DatoImportado(DatoImportadoBase):
    """Esquema de dato importado (lectura)."""
    
    class Config:
        from_attributes = True
    
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
    
    class Config:
        from_attributes = True
    
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
