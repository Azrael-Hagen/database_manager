# GUÍA RÁPIDA - Database Manager con Docker

## 🚀 INICIO RÁPIDO (Recomendado)

### Opción 1: Script Automático (RECOMENDADO)

#### Windows:
1. **Abre PowerShell** (Win + X → Windows PowerShell o PowerShell)
2. **Navega al proyecto**:
   ```powershell
   cd "c:\Users\Azrael\OneDrive\Documentos\Herramientas\database_manager"
   ```
3. **Ejecuta el script**:
   ```powershell
   .\start-docker.bat
   ```
4. **Espera a que termine** (verás "SUCCESS - Services Running!")
5. **Abre el navegador**:
   - Web: http://localhost:8000
   - API Docs: http://localhost:8000/docs

#### Linux / macOS:
```bash
cd ~/path/to/database_manager
chmod +x start-docker.sh
./start-docker.sh
# Abre http://localhost:8000 en el navegador
```

---

## 📋 PASO A PASO MANUAL (Si prefieres control total)

### PASO 1: Verificar Docker está instalado

```powershell
docker --version
docker-compose --version
```

**Esperado**: Deberías ver versiones de Docker y docker-compose.

Si no está instalado:
- Descarga Docker Desktop: https://www.docker.com/products/docker-desktop
- Asegúrate de que Docker Desktop esté corriendo (ícono en la bandeja del sistema)

---

### PASO 2: Navegar al proyecto

```powershell
cd "c:\Users\Azrael\OneDrive\Documentos\Herramientas\database_manager"
```

Verifica que ves estos archivos:
- `docker-compose.yml`
- `.env`
- `Dockerfile`

---

### PASO 3: Construir e iniciar servicios

```powershell
docker-compose up -d --build
```

Para usar hostname sin puerto (`http://phantom.database.local`), inicia también el perfil de proxy local:

```powershell
docker-compose --profile local-host up -d --build
```

**Qué hace**:
- `up`: Inicia contenedores
- `-d`: En segundo plano (detached mode)
- `--build`: Reconstruye imágenes (primera vez tardará 2-3 minutos)

**Esperado**: Verás algo como:
```
Creating database_manager_db ... done
Creating database_manager_api ... done
```

---

### PASO 4: Verificar que los servicios están running

```powershell
docker-compose ps
```

**Esperado**:
```
NAME                          STATUS
database_manager_db           Up (healthy)
database_manager_api          Up
```

Si MariaDB no está `healthy` aún, espera 30-40 segundos y vuelve a ejecutar.

---

### PASO 5: Abre el navegador y accede

**Opción A - Web UI** (La más fácil):
```
http://localhost:8000
```

**Opción A2 - Hostname local sin puerto**:
```
http://phantom.database.local
```

**Opción B - API Documentation** (Swagger):
```
http://localhost:8000/docs
```

**Opción C - ReDoc** (Documentación alternativa):
```
http://localhost:8000/redoc
```

---

### PASO 6: LOGIN - Usa credenciales por defecto

```
Usuario:    admin
Contraseña: SecurePassword123!
```

---

## 🌐 ACCESO DESDE RED LOCAL Y OTRAS REDES

### Red local sin escribir IP

Configura un hostname local para abrir la app desde celulares/PCs con una URL fija:

Comando automático (Windows):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup-phantom-host.ps1
```

Este script:

1. Detecta tu IP local.
2. Agrega/actualiza `phantom.database.local` en `hosts`.
3. Limpia caché DNS.
4. Configura acceso sin puerto (`80 -> 8000`).

```env
API_HOST=0.0.0.0
API_PORT=8000
LOCAL_HOSTNAME=phantom.database.local
PUBLIC_BASE_URL=http://phantom.database.local
```

Opciones para resolver `phantom.database.local`:

1. DNS local del router (recomendado): registro A al equipo servidor.
2. Archivo `hosts` en cada cliente:
   - Windows: `C:\Windows\System32\drivers\etc\hosts`
   - Linux/macOS: `/etc/hosts`
   - Ejemplo: `192.168.1.50 phantom.database.local`

Para no usar puerto en la URL, publica el servicio en `:80` con reverse proxy:

1. Cliente entra a `http://phantom.database.local`
2. Proxy escucha `:80`
3. Proxy reenvía al backend `http://127.0.0.1:8000`

En Docker de este proyecto, el proxy local se activa con:

```powershell
docker-compose --profile local-host up -d
```

### Acceso desde internet (otras redes)

1. Configura DDNS o dominio público.
2. Abre/reenruta puertos en router hacia el servidor.
3. Usa reverse proxy con HTTPS (Nginx/Caddy).
4. Define `PUBLIC_BASE_URL` al dominio público:

```env
PUBLIC_BASE_URL=https://tu-dominio.com
```

Con esto, la UI y los QR públicos dejan de depender de `localhost`.

---

## ✅ CHECKLIST DE PUESTA EN PRODUCCIÓN SEGURA

1. DNS/hosts resuelve `phantom.database.local` al servidor correcto.
2. `PUBLIC_BASE_URL` configurado:
   - LAN: `http://phantom.database.local`
   - Internet: `https://tu-dominio.com`
3. Reverse proxy activo (Nginx/Caddy) en `80/443`.
4. Backend escuchando solo internamente o por red privada (`API_HOST=0.0.0.0`, `API_PORT=8000`).
5. Firewall abierto solo para `80/443` (y no exponer `8000` públicamente).
6. HTTPS y certificado TLS válidos para acceso externo.
7. Contraseñas y `SECRET_KEY` actualizadas.
8. Respaldos semanales verificados y restauración documentada.
9. Prueba cruzada:
   - PC en LAN abre `http://phantom.database.local`
   - Móvil en WiFi abre `http://phantom.database.local`
   - QR público abre dominio correcto (sin `localhost`).

---

## ✅ VERIFICAR QUE TODO FUNCIONA

### Test 1: Acceder al Dashboard
1. Abre http://localhost:8000
2. Haz login con admin/SecurePassword123!
3. Deberías ver el dashboard

### Test 2: Crear un usuario
1. En el navegador, en la sección "Usuarios"
2. Haz clic en "Agregar Usuario"
3. Completa los datos
4. Verifica que aparece en la lista

### Test 3: Importar datos (CSV)
1. Ve a la sección "Importar Datos"
2. Prepara un CSV con columnas: `nombre,email,telefono,empresa`
3. Ejemplo:
   ```
   nombre,email,telefono,empresa
   Juan,juan@example.com,1234567890,Acme Corp
   María,maria@example.com,0987654321,Tech Inc
   ```
4. Sube el archivo
5. Verifica que aparecen en "Datos Importados" con QR generados

### Test 4: Escaneo QR / Código de barras
1. Ve a la sección "QR Verificación"
2. Usa "Escanear con Cámara"
3. Prueba un QR generado por el sistema (URL pública)
4. Prueba un código numérico (ID / teléfono) desde lector/barcode
5. Verifica que el estado de pago se muestra correctamente

---

## 📊 MONITOREAR EL PROYECTO

### Ver logs en tiempo real

**Backend (API):
```powershell
docker-compose logs -f backend
```

**MariaDB (Base de datos):
```powershell
docker-compose logs -f mariadb
```

**Todo (todos los servicios):
```powershell
docker-compose logs -f
```

**Salir de logs**: Presiona `Ctrl + C`

---

### Ver estado de contenedores

```powershell
docker-compose ps
```

---

## 🛑 DETENER / REINICIAR

### Modo local (sin Docker)
```cmd
stop.bat
```

Esto cierra procesos escuchando en `:8000` para evitar sesiones huérfanas.

### Detener servicios (mantiene datos)
```powershell
docker-compose down
```

### Detener y eliminar datos (reset total)
```powershell
docker-compose down -v
```

### Reiniciar servicio específico
```powershell
docker-compose restart backend
docker-compose restart mariadb
```

---

## 🔧 SOLUCIONAR PROBLEMAS

### Problema: "Docker daemon is not running"
**Solución**: Abre Docker Desktop. Espera a que esté listo (ícono en bandeja).

### Problema: Puerto 8000 o 3306 ya en uso
**Solución**: 
```powershell
# Ver qué está usando el puerto
netstat -ano | findstr :8000
# Cierra la aplicación o cambia el puerto en docker-compose.yml
```

### Problema: MariaDB no inicia o tarda mucho
**Solución**: Es normal. Espera 1-2 minutos. Verifica con:
```powershell
docker-compose logs mariadb
```

### Problema: Error "cannot find file init.sql"
**Solución**: El directorio `scripts/` debe existir:
```powershell
# Verifica que existe
Test-Path scripts\init.sql
# Si no existe, crea el directorio
mkdir scripts
# Se crea automáticamente al iniciar
```

### Problema: No puedo conectar a la API
**Solución**:
1. Verifica que los servicios están running: `docker-compose ps`
2. Espera 30 segundos después de arrancar
3. Revisa logs: `docker-compose logs backend`
4. Si aún falla, reinicia:
   ```powershell
   docker-compose down
   docker-compose up -d --build
   ```

---

## 📝 ESTRUCTURA DEL PROYECTO

```
database_manager/
├── docker-compose.yml          ← Configuración de servicios
├── Dockerfile                  ← Imagen del backend
├── .env                        ← Variables de entorno (EDITADO CON CLAVE SEGURA)
├── start-docker.bat           ← Script de inicio Windows
├── start-docker.sh            ← Script de inicio Linux/macOS
├── backend/
│   ├── main.py               ← Servidor FastAPI
│   ├── requirements.txt       ← Dependencias Python
│   ├── app/
│   │   ├── api/              ← Rutas API
│   │   ├── models.py         ← Modelos BD
│   │   └── database/         ← ORM y repositorios
│   └── init_db.py            ← Script inicialización BD
├── web/
│   ├── index.html            ← Dashboard web
│   ├── css/                  ← Estilos
│   └── js/                   ← JavaScript interactivo
├── frontend/                 ← GUI Tkinter (opcional)
├── scripts/
│   └── init.sql              ← SQL de inicialización
└── tests/                    ← Tests unitarios
```

---

## 🔐 SEGURIDAD - IMPORTANTE PARA PRODUCCIÓN

**Cambios ya realizados**:
- ✅ SECRET_KEY: Generada criptográficamente
- ✅ .env: Configurado con credenciales de desarrollo

**Antes de desplegar a producción**:
1. Cambia la contraseña admin:
   ```
   Actual: SecurePassword123!
   Nueva: Una fuerte (>=12 caracteres, mayúsculas, números, símbolos)
   ```
2. Cambia credenciales de BD en `.env`:
   ```
   DB_PASSWORD=TU_CONTRASEÑA_SEGURA
   ```
3. Genera nuevamente SECRET_KEY:
   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
4. Cambia a HTTPS

---

## 🎯 PRÓXIMOS PASOS

1. **Practica el flujo completo**: Login → Crear usuario → Importar CSV → Ver datos
2. **Customiza campos**: Edita modelos en `backend/app/models.py`
3. **Crea tests**: Copia en `tests/` siguiendo el patrón existente
4. **Despliega**: Usa `docker-compose` en tu servidor

---

## ❓ AYUDA RÁPIDA

- **API Docs**: http://localhost:8000/docs (prueba endpoints aquí)
- **Logs**: `docker-compose logs -f` (monitorea en tiempo real)
- **Estado**: `docker-compose ps` (verifica servicios)
- **Reset**: `docker-compose down -v` (limpia y comienza de nuevo)

¡Listo! Ejecuta `start-docker.bat` y disfruta tu Database Manager. 🚀
