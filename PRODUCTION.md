# Database Manager - PRODUCCIÓN

Aplicación profesional de gestión de base de datos con autenticación, auditoría y QR.

## 🚀 Deployment Rápido

### Con Docker Compose (Recomendado)

```bash
# Linux / Mac
chmod +x deploy.sh
./deploy.sh

# O manualmente
docker-compose up -d
docker-compose exec backend python init_db.py
```

### En Windows (Sin Docker)

```powershell
# Ejecutar PowerShell como administrador
.\deploy.ps1

# Luego iniciar servidor
cd backend
python main.py
```

### Manual (Cualquier sistema)

```bash
# 1. Editar .env con credenciales
cp .env.example .env
# Editar .env

# 2. Backend
cd backend
pip install -r requirements.txt
python init_db.py
python main.py

# 3. En otra terminal - Frontend (opcional)
cd frontend
pip install -r requirements.txt
python main.py
```

## 📊 URLs

- **API REST**: http://localhost:8000/api
- **Documentación Swagger**: http://localhost:8000/docs
- **Documentación ReDoc**: http://localhost:8000/redoc
- **Panel Web**: http://localhost:8000
- **MariaDB**: localhost:3306

## 🔐 Autenticación

### Credenciales por Defecto

- **Usuario**: admin
- **Contraseña**: SecurePassword123!

**⚠️ CAMBIAR INMEDIATAMENTE EN PRODUCCIÓN**

### Endpoints de Auth

```bash
# Registrar usuario
POST /api/auth/registrar
Content-Type: application/json
{
  "username": "usuario",
  "email": "user@example.com",
  "password": "SecurePass123!",
  "nombre_completo": "Nombre Completo"
}

# Login
POST /api/auth/login
{
  "username": "usuario",
  "password": "SecurePass123!"
}

# Obtener usuario actual
GET /api/auth/me
Authorization: Bearer {token}
```

## 📁 Importación de Datos

### CSV

```bash
POST /api/import/csv
Content-Type: multipart/form-data

archivo: (file)
tabla: datos_importados
delimitador: ,
```

### Excel

```bash
POST /api/import/excel
Content-Type: multipart/form-data

archivo: (file)
tabla: datos_importados
hoja: 0
```

## 📊 API CRUD de Datos

```bash
# Listar (con paginación y búsqueda)
GET /api/datos/?pagina=1&por_pagina=10&buscar=juan

# Obtener uno
GET /api/datos/{id}

# Crear
POST /api/datos/
{
  "nombre": "Juan",
  "email": "juan@example.com",
  "telefono": "123456789"
}

# Actualizar
PUT /api/datos/{id}
{
  "nombre": "Juan Pérez"
}

# Eliminar (soft delete)
DELETE /api/datos/{id}
```

## 🔄 Importación en Background

La importación se procesa en background para no bloquear la API.

```bash
# Obtener estado
GET /api/import/estado/{importacion_id}

Response:
{
  "status": "success",
  "data": {
    "id": 1,
    "estado": "SUCCESS",
    "registros_importados": 1000,
    "duracion_segundos": 45
  }
}
```

## 📋 Características

✅ **Autenticación JWT** - Token basado  
✅ **Auditoría completa** - Registro de todas las acciones  
✅ **QR automático** - Genera QR para cada registro  
✅ **Paginación** - Manejo de datos grandes  
✅ **Búsqueda/Filter** - Búsquedas avanzadas  
✅ **Soft Delete** - Eliminación lógica  
✅ **Logging** - Logs detallados en archivo  
✅ **Rate Limiting** - Protección contra abuso  
✅ **Swagger/OpenAPI** - Documentación automática  
✅ **Tests** - Suite completa de tests  

## 🐳 Docker

### Build image
```bash
docker build -t database-manager:latest .
```

### Run container
```bash
docker run -d -p 8000:8000 \
  -e DB_HOST=localhost \
  -e DB_USER=manager \
  -e DB_PASSWORD=secure123 \
  --name db-manager \
  database-manager:latest
```

### Con Docker Compose
```bash
docker-compose up -d
```

## 🔧 Configuración

Editar `.env`:

```
# Base de Datos
DB_HOST=localhost
DB_USER=manager
DB_PASSWORD=secure_password
DB_NAME=database_manager
DB_PORT=3306

# API
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=False

# Seguridad
SECRET_KEY=cambiar-en-produccion
LOG_LEVEL=INFO
```

## 📊 Estructura de Tablas

### usuarios
- id (PK)
- username
- email
- hashed_password
- nombre_completo
- es_activo
- es_admin
- fecha_creacion
- fecha_ultima_sesion

### datos_importados
- id (PK)
- uuid
- nombre
- email
- telefono
- empresa
- ciudad
- pais
- qr_code (BLOB)
- qr_filename
- creado_por (FK)
- importacion_id (FK)
- fecha_creacion
- fecha_modificacion
- es_activo (para soft delete)

### import_logs
- id (PK)
- uuid
- archivo_nombre
- tipo_archivo
- tabla_destino
- registros_importados
- registros_fallidos
- estado
- usuario_id (FK)
- fecha_inicio
- fecha_fin

### auditoria_acciones
- id (PK)
- usuario_id (FK)
- tipo_accion
- tabla
- registro_id
- descripcion
- datos_anteriores (JSON)
- datos_nuevos (JSON)
- ip_origen
- fecha

## 🧪 Tests

```bash
cd backend
pytest tests/ -v --cov
```

## 📝 Logs

Los logs se guardan en:
- `backend/logs/app.log`

Ver en tiempo real:
```bash
tail -f backend/logs/app.log
```

O si usas Docker:
```bash
docker-compose logs -f backend
```

## 🚨 Troubleshooting

### Error de conexión a BD
```bash
# Verificar que MariaDB está corriendo
docker ps | grep mariadb

# Verificar credenciales en .env
cat .env | grep DB_
```

### Puerto en uso
```bash
# Windows
netstat -ano | findstr :8000

# Linux
lsof -i :8000
```

### Reiniciar servicios
```bash
docker-compose restart
```

### Ver logs de error
```bash
docker-compose logs backend
```

## 📞 Soporte

Para más información revisa:
- [Documentación de API](docs/API.md)
- [Arquitectura](docs/ARCHITECTURE.md)
- [Setup detallado](docs/SETUP.md)

---

**Versión**: 1.0.0  
**Última actualización**: 2026-03-21  
**Licencia**: MIT
