# CHECKPOINT OPERATIVO 2026-03-23 - AUTOSTART POWERSHELL + BLUE-GREEN + E2E

## Objetivo
Corregir fallo de ejecución de autostart en PowerShell, endurecer estrategia de despliegue sin downtime y validar operación E2E.

## Cambios aplicados

### 1) Corrección crítica en Dashboard
- Archivo: `backend/app/api/dashboard.py`
- Se eliminó texto contaminado incrustado accidentalmente en SQL del `ORDER BY`.
- Resultado: se restablece consulta de agentes recientes sin errores de SQL.

### 2) Autostart compatible con PowerShell
- Archivo: `web/js/main.js`
  - Comando copiado en UI actualizado a `./manage_autostart.bat ...`.
- Archivo: `web/index.html`
  - Texto de ayuda actualizado a comando base con prefijo relativo (`.\manage_autostart.bat ...`).
- Archivo: `README.md`
  - Se agregó bloque explícito de comandos autostart para PowerShell.

### 3) Despliegue robusto sin downtime (blue-green)
- Nuevo archivo: `docker-compose.bluegreen.yml`
  - Servicios: `backend_blue`, `backend_green`, `gateway` (nginx), `mariadb`.
  - Healthchecks en ambos backends.
- Nuevo archivo: `deploy/nginx.bluegreen.conf`
  - Proxy estable por puerto 80.
- Nuevo archivo: `deploy/active-upstream.conf`
  - Selector activo blue/green para switch atómico.
- Nuevo archivo: `scripts/deploy-bluegreen.ps1`
  - Deploy/switch/status para Windows.
- Nuevo archivo: `scripts/deploy-bluegreen.sh`
  - Deploy/switch/status para Linux/macOS.
- Archivo actualizado: `README.md`
  - Instrucciones de deploy blue-green para Windows/Linux.

## Validación realizada

### Sanidad de backend
- Comando: `python -c "import sys; sys.path.append('backend'); import main; print('OK')"`
- Resultado: `OK`.

### Autostart en PowerShell
- Comando: `.\manage_autostart.bat status`
- Resultado: el comando ya se reconoce y ejecuta; respondió que la tarea no existe (estado esperado si aún no está instalada).

### E2E en servidor activo
- Flujo validado con script HTTP real:
  - `POST /api/auth/login`
  - `GET /api/auth/me`
  - `GET /api/dashboard/summary`
  - `GET /api/network/local`
- Resultado: `E2E_OK` con respuestas `200` en endpoints clave.

## Observaciones
- La suite heredada `tests/test_api.py` no es confiable actualmente para regresión rápida porque asume esquema SQLite distinto al modelo actual (falla por tabla `usuarios` inexistente en setup de prueba).
- Se recomienda modernizar esos tests para el esquema vigente o migrarlos a pruebas de integración con DB de test compatible.

## Impacto en Linux
- Se incorporó ruta de despliegue portable con script `scripts/deploy-bluegreen.sh` y `docker compose`.
- Requerimientos mínimos en Linux:
  - Docker + Compose plugin.
  - Variables de entorno (`.env`) con credenciales reales.
  - Puerto 80 disponible para `gateway`.
  - Copia/restauración de DB compatible con MariaDB objetivo.

## Rollback operativo
- Con blue-green, rollback inmediato mediante switch del upstream al color anterior:
  - PowerShell: `./scripts/deploy-bluegreen.ps1 -Action switch -Color blue|green`
  - Linux: `./scripts/deploy-bluegreen.sh switch blue|green`
