# Database Manager

Aplicación para administración de MariaDB con interfaz web moderna, autenticación JWT, importación de archivos y herramientas SQL avanzadas.

## Características

- Gestión de bases de datos: listar bases, tablas, ver datos y eliminar tablas.
- Visualizar Datos con contexto real de BD+tabla (selector de base de datos y consulta exacta por ID/UUID).
- Herramientas SQL avanzadas: ejecutar consultas completas SQL desde UI.
- Importación de archivos: CSV, Excel, TXT y DAT.
- Importación adaptable: CSV/TXT/DAT se ajustan a tablas existentes (agrega columnas faltantes).
- Gestión de usuarios: CRUD de usuarios, roles y cambio de contraseña.
- Auditoría: registro de acciones con vista en interfaz.
- Módulo QR mejorado: lectura clara por cámara o entrada manual (QR + código de barras).
- Gestión de líneas: inventario de líneas y asignación agente-línea con estado ocupada/libre.
- Alta manual de agentes: formulario rápido (Nombre, alias, ubicación, FP, FC, grupo) con asignación de línea automática o manual.
- Catálogo de ladas: filtros por lada y preferencia por agente para priorizar asignación automática.
- Tiempo real configurable: actualización periódica con modo ligero para ahorrar recursos.

## Requisitos

- Python 3.14+
- MariaDB 12+
- Windows/Linux/macOS

## Inicio rápido (Windows)

```cmd
cd C:\ruta\database_manager
start.bat
```

Accesos:

- App: http://localhost:8000
- API Docs: http://localhost:8000/docs

Detener servidor en cualquier momento:

```cmd
stop.bat
```

Credenciales iniciales:

- Usuario: admin
- Contraseña: Admin123!

## Uso básico

1. Inicia sesión con usuario administrador.
2. En Bases de Datos: carga bases, explora tablas y ejecuta SQL.
3. En Visualizar Datos: selecciona base y tabla para consultar registros exactos.
4. En QR: valida por escaneo y administra líneas ocupadas/libres por agente.
5. En QR > Agentes y Líneas: crea agentes manualmente y asigna número por modo automático/manual.
6. En QR > Agentes y Líneas: usa ladas para filtrar inventario y orientar asignaciones.
7. En Importar: selecciona archivo, delimitador y tabla destino.
8. En Usuarios: crea, edita y administra cuentas.
9. En Auditoría: revisa actividad reciente.

## Branding (logo y nombre)

Se agregó carpeta para recursos visuales en:

- `web/sources/`

Configura el nombre mostrado en navegador/navbar y la ruta del logo editando:

- `web/sources/branding.json`

Ejemplo:

```json
{
	"appName": "Mi Operación",
	"subtitle": "Base Agentes 2026",
	"logoPath": "sources/logo.png"
}
```

Luego coloca tu logo en `web/sources/logo.png` (o cambia `logoPath` a otra imagen de la carpeta).

## Configuración de tiempo real

En Dashboard puedes configurar:

- Tiempo real: ON/OFF
- Intervalo: 10s / 20s / 30s / 60s

Modo ligero incorporado:

- Si la pestaña está inactiva, pausa auto-refresh.
- Al volver a la pestaña, reanuda según configuración.

## Acceso desde red local y remoto

### Red local (sin escribir IP en cada dispositivo)

La app ahora usa la misma URL desde la que se abre el sitio, por lo que no fuerza `localhost` en frontend ni en QR.

Puedes configurar un hostname local en tu `.env`:

```env
API_HOST=0.0.0.0
API_PORT=8000
LOCAL_HOSTNAME=phantom.database.local
PUBLIC_BASE_URL=http://phantom.database.local
```

Opciones para resolver `phantom.database.local` en tu red:

1. DNS del router (recomendado): crea un registro A apuntando al equipo servidor.
2. Archivo hosts en cada cliente:
	- Windows: `C:\Windows\System32\drivers\etc\hosts`
	- Linux/macOS: `/etc/hosts`
	- Ejemplo: `192.168.1.50 phantom.database.local`
3. mDNS/Bonjour en LAN (si tu red lo soporta).

### Acceso remoto (otras redes)

Para entrar desde internet, necesitas publicar tu servidor de forma segura:

1. IP fija o DDNS (`tudominio.duckdns.org`, por ejemplo).
2. Redirección de puertos en router (mejor si usas reverse proxy).
3. HTTPS con certificado TLS (Nginx/Caddy recomendado).
4. Firewall permitiendo solo puertos necesarios.
5. Definir `PUBLIC_BASE_URL` al dominio público:

```env
PUBLIC_BASE_URL=https://tu-dominio.com
```

Con esto, los enlaces QR públicos se generan con ese dominio y no con `localhost`.

Si no quieres escribir puerto en LAN, usa reverse proxy en `:80` apuntando al backend `:8000`.

## Estructura principal

```text
backend/        API FastAPI + modelos + seguridad
web/            Interfaz HTML/CSS/JS
web/sources/    Logo e identidad visual (branding.json + imágenes)
start.bat       Arranque local en Windows
```

## API principal

- `POST /api/auth/login`
- `GET /api/auth/me`
- `GET /api/databases/`
- `GET /api/databases/{db}/tables`
- `GET /api/databases/{db}/tables/{table}`
- `POST /api/databases/{db}/query`
- `POST /api/import/csv`
- `POST /api/import/excel`
- `POST /api/import/txt`
- `POST /api/import/dat`
- `GET /api/import/estado/{id}`
- `GET /api/usuarios/`
- `PUT /api/usuarios/{id}/password`
- `GET /api/auditoria/`
- `POST /api/qr/scan/verify` (valida contenido escaneado QR/codigo de barras)
- `GET /api/qr/agentes` (agentes activos con líneas asignadas)
- `POST /api/qr/agentes/manual` (alta manual de agente con asignación opcional)
- `GET /api/qr/lineas` (inventario de líneas y ocupación)
- `POST /api/qr/lineas` (crear/reactivar línea)
- `POST /api/qr/lineas/{linea_id}/asignar`
- `POST /api/qr/lineas/{linea_id}/liberar`
- `DELETE /api/qr/lineas/{linea_id}`
- `GET /api/qr/ladas` (catálogo de ladas activas)
- `POST /api/qr/ladas` (crear/reactivar lada)
- `POST /api/databases/{db}/views` (crear/actualizar vista temporal)
- `GET /api/databases/{db}/views`
- `DELETE /api/databases/{db}/views/{view}`

## Estado

- Producción local estable
- Ciclo de vida FastAPI migrado a lifespan (sin warning de on_event)
- E2E validado en login, SQL avanzada, importación adaptable, vistas SQL, lectura QR/barcode y ocupación de líneas

## Licencia

MIT
