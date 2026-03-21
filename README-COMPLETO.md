# 📊 Database Manager - Guía Completa

**Versión:** 1.0.0 | **Estado:** PRODUCCIÓN | **Última actualización:** 2026

## 📋 Descripción

Sistema completo de gestión de bases de datos MariaDB con:
- ✅ Panel web moderno y responsivo (HTML5/CSS3/JS)
- ✅ API REST completa con autenticación JWT
- ✅ Importación de archivos (CSV, Excel, TXT, DAT) con delimitadores personalizados
- ✅ Generación automática de códigos QR
- ✅ Sistema de auditoría completo
- ✅ Autenticación y autorización
- ✅ Docker Compose para despliegue

---

## 🚀 Inicio Rápido

### Windows (PowerShell):
```powershell
cd C:\ruta\del\proyecto
.\deploy.ps1
```

### Linux/Mac (Bash):
```bash
cd /ruta/del/proyecto
chmod +x deploy.sh
./deploy.sh
```

### Docker (Recomendado):
```bash
docker-compose up
```

---

## 📁 Estructura del Proyecto

```
database_manager/
├── backend/                          # API FastAPI
│   ├── app/
│   │   ├── models.py                # SQLAlchemy ORM
│   │   ├── schemas.py               # Pydantic validation
│   │   ├── security.py              # JWT + bcrypt
│   │   ├── database/
│   │   │   ├── orm.py               # Session management
│   │   │   └── repositorios.py      # Repository pattern
│   │   ├── api/
│   │   │   ├── auth.py              # Endpoints auth
│   │   │   ├── datos.py             # CRUD endpoints
│   │   │   └── importacion.py       # Import endpoints
│   ├── main.py                      # FastAPI app
│   ├── requirements.txt              # Dependencias
│   └── logs/                         # Archivos de log
├── web/                              # Frontend web
│   ├── index.html                   # UI principal
│   ├── css/
│   │   └── style.css                # Estilos
│   └── js/
│       ├── api-client.js            # Cliente HTTP
│       └── main.js                  # Lógica frontend
├── frontend/                         # PyQt5 Desktop (futuro)
├── Dockerfile                        # Contenedorización
├── docker-compose.yml               # Orquestación
├── deploy.sh                         # Script Linux/Mac
└── deploy.ps1                        # Script Windows

```

---

## ⚙️ Configuración

### Variables de Entorno (.env)

Crea un archivo `.env` en la raíz del proyecto:

```env
# Base de Datos
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=tu_password
DB_NAME=database_manager

# API
API_HOST=0.0.0.0
API_PORT=8000
SECRET_KEY=tu_clave_secreta_super_larga

# JWT
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=30

# QR
QR_OUTPUT_DIR=./qr_codes
```

---

## 📦 Instalación

### Opción 1: Instalación Manual

#### 1. Crear entorno virtual
```bash
# Windows
python -m venv backend\venv
backend\venv\Scripts\activate

# Linux/Mac
python3 -m venv backend/venv
source backend/venv/bin/activate
```

#### 2. Instalar dependencias
```bash
pip install -r backend/requirements.txt
```

#### 3. Iniciar servidor
```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Opción 2: Docker Compose

```bash
# Construir e iniciar
docker-compose up

# En background
docker-compose up -d

# Detener
docker-compose down
```

---

## 🌐 Acceso a la Aplicación

| Componente | URL |
|-----------|-----|
| **Panel Web** | http://localhost:8000 |
| **API Docs (Swagger)** | http://localhost:8000/docs |
| **ReDoc** | http://localhost:8000/redoc |
| **Health Check** | http://localhost:8000/api/health |

---

## 🔐 Autenticación

### Registrar usuario (Primera vez)

```javascript
// En consola del navegador
fetch('http://localhost:8000/api/auth/registrar', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        username: 'admin',
        email: 'admin@example.com',
        password: 'Segura123!',
        nombre_completo: 'Administrador'
    })
})
```

### Login

```javascript
const response = await fetch('http://localhost:8000/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        username: 'admin',
        password: 'Segura123!'
    })
});

const data = await response.json();
console.log('Token:', data.access_token);
localStorage.setItem('authToken', data.access_token);
```

---

## 📚 API Endpoints

### Autenticación

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/auth/registrar` | Crear cuenta |
| POST | `/api/auth/login` | Iniciar sesión |
| GET | `/api/auth/me` | Obtener usuario actual |

### Datos

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/datos` | Listar todos (paginado) |
| GET | `/api/datos/{id}` | Obtener por ID |
| GET | `/api/datos/uuid/{uuid}` | Obtener por UUID |
| POST | `/api/datos` | Crear registro |
| PUT | `/api/datos/{id}` | Actualizar registro |
| DELETE | `/api/datos/{id}` | Eliminar (soft delete) |

### Importación

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/import/csv` | Importar CSV |
| POST | `/api/import/excel` | Importar Excel |
| GET | `/api/import/estado/{id}` | Estado de importación |

### Auditoría

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/auditoria` | Ver log de auditoría |

---

## 🔄 Flujo de Importación

```
1. Usuario selecciona archivo
2. Especifica delimitador
3. Hace POST a /api/import/{tipo}
4. Backend:
   - Valida estructura
   - Genera QR por fila
   - Inserta en BD
   - Retorna importacion_id
5. Cliente sondea /api/import/estado/{id}
6. Muestra progreso
7. Muestra resultado final
```

---

## 🗄️ Base de Datos

### Tablas

#### `usuarios`
```sql
CREATE TABLE usuarios (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    nombre_completo VARCHAR(120),
    es_admin BOOLEAN DEFAULT FALSE,
    ultima_sesion DATETIME,
    es_activo BOOLEAN DEFAULT TRUE,
    creado_en DATETIME DEFAULT NOW(),
    actualizado_en DATETIME ON UPDATE NOW()
);
```

#### `datos_importados`
```sql
CREATE TABLE datos_importados (
    id INT PRIMARY KEY AUTO_INCREMENT,
    usuario_id INT,
    nombre VARCHAR(255),
    email VARCHAR(120),
    empresa VARCHAR(120),
    contenido_qr TEXT,
    uuid VARCHAR(36) UNIQUE,
    es_activo BOOLEAN DEFAULT TRUE,
    creado_en DATETIME DEFAULT NOW(),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);
```

#### `import_logs`
```sql
CREATE TABLE import_logs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    usuario_id INT,
    archivo_nombre VARCHAR(255),
    total_registros INT,
    registros_exitosos INT,
    registros_fallidos INT,
    estado VARCHAR(20),
    mensaje_error TEXT,
    duracion_segundos INT,
    uuid VARCHAR(36) UNIQUE,
    creado_en DATETIME DEFAULT NOW(),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);
```

#### `auditoria_acciones`
```sql
CREATE TABLE auditoria_acciones (
    id INT PRIMARY KEY AUTO_INCREMENT,
    usuario_id INT,
    tipo_accion VARCHAR(50),
    tabla_afectada VARCHAR(100),
    registro_id INT,
    detalles JSON,
    ip_origen VARCHAR(45),
    fecha_hora DATETIME DEFAULT NOW(),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);
```

---

## 🔍 Ejemplos de Uso

### Ejemplo 1: Importar datos desde JavaScript

```javascript
const file = document.getElementById('fileInput').files[0];
const formData = new FormData();
formData.append('file', file);

fetch('http://localhost:8000/api/import/csv', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}` },
    body: formData
}).then(r => r.json())
  .then(data => console.log('Import ID:', data.importacion_id));
```

### Ejemplo 2: Buscar datos

```javascript
fetch('http://localhost:8000/api/datos?search=email@example.com&page=1&limit=50', {
    headers: { 'Authorization': `Bearer ${token}` }
}).then(r => r.json())
  .then(data => console.log('Resultados:', data.datos));
```

### Ejemplo 3: Usar API Client

```javascript
// Ya incluido en index.html
const client = new APIClient('http://localhost:8000/api');

// Login
const data = await client.login('username', 'password');
client.setToken(data.access_token);

// Obtener datos
const response = await client.getDatos(1, 50, 'búsqueda');

// Importar CSV
const file = document.getElementById('fileInput').files[0];
const result = await client.importarCSV(file);
```

---

## 🐛 Troubleshooting

### "Port already in use"
```bash
# Cambiar puerto
uvicorn main:app --port 8001

# O matar proceso en Windows
netstat -ano | findstr :8000
taskkill /PID {PID} /F
```

### "MySQL/MariaDB connection error"
- Verificar credenciales en `.env`
- Verificar que MariaDB esté ejecutándose: `mysql -u root -p`

### "ModuleNotFoundError"
```bash
# Verificar venv activo
which python  # Linux/Mac
where python  # Windows

# Reinstalar dependencias
pip install --no-cache-dir -r requirements.txt
```

### "CORS error"
- Verificar que FastAPI tenga CORS habilitado (en main.py)
- Agregar dominio a allowed_origins

---

## 📊 Monitoreo

### Ver logs
```bash
# Backend
tail -f backend/logs/app.log

# Docker
docker-compose logs -f backend
```

### Health Check
```bash
curl http://localhost:8000/api/health
```

### Estadísticas
```bash
# Obtener stats del servidor
curl -H "Authorization: Bearer {token}" \
     http://localhost:8000/api/datos?page=1&limit=1
```

---

## 🔐 Seguridad

- ✅ Contraseñas hasheadas con bcrypt
- ✅ JWT tokens con 30 minutos de expiración
- ✅ CORS configurado
- ✅ Rate limiting en Nginx (30 req/s)
- ✅ SQL injection prevention (SQLAlchemy ORM)
- ✅ Audit trail completo
- ✅ Soft delete para cumplimiento legal

---

## 📈 Producción

### Recomendaciones

1. **HTTPS obligatorio**
   - Usar certificados SSL/TLS
   - Nginx con proxy inverso

2. **Backups automáticos**
   - MariaDB dumps diarios
   - Replicación master-slave

3. **Monitoreo**
   - Prometheus + Grafana
   - ELK Stack para logs

4. **Escalabilidad**
   - Load balancer (HAProxy)
   - múltiples instancias API
   - Redis para cache

---

## 📝 Licencia

MIT License - Libre para uso comercial y personal

---

## 👨‍💻 Soporte

Para reportar issues o sugerencias, contactar al equipo de desarrollo.

---

**Última actualización:** Enero 2026
**Versión:** 1.0.0 - PRODUCCIÓN
