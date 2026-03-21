# Database Manager

Aplicación para administración de MariaDB con interfaz web moderna, autenticación JWT, importación de archivos y herramientas SQL avanzadas.

## Características

- Gestión de bases de datos: listar bases, tablas, ver datos y eliminar tablas.
- Herramientas SQL avanzadas: ejecutar consultas completas SQL desde UI.
- Importación de archivos: CSV, Excel, TXT y DAT.
- Importación adaptable: CSV/TXT/DAT se ajustan a tablas existentes (agrega columnas faltantes).
- Gestión de usuarios: CRUD de usuarios, roles y cambio de contraseña.
- Auditoría: registro de acciones con vista en interfaz.
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

Credenciales iniciales:

- Usuario: admin
- Contraseña: Admin123!

## Uso básico

1. Inicia sesión con usuario administrador.
2. En Bases de Datos: carga bases, explora tablas y ejecuta SQL.
3. En Importar: selecciona archivo, delimitador y tabla destino.
4. En Usuarios: crea, edita y administra cuentas.
5. En Auditoría: revisa actividad reciente.

## Configuración de tiempo real

En Dashboard puedes configurar:

- Tiempo real: ON/OFF
- Intervalo: 10s / 20s / 30s / 60s

Modo ligero incorporado:

- Si la pestaña está inactiva, pausa auto-refresh.
- Al volver a la pestaña, reanuda según configuración.

## Estructura principal

```text
backend/        API FastAPI + modelos + seguridad
web/            Interfaz HTML/CSS/JS
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

## Estado

- Producción local estable
- E2E validado en login, SQL avanzada, importación adaptable y cambio de contraseña

## Licencia

MIT
