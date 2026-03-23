# CHECKPOINT OPERATIVO 2026-03-23 - DEPLOY ROOT ROBUSTO

## Objetivo
Probar flujo de deploy solicitado por error reportado y habilitar ejecución robusta desde directorio raíz.

## Hallazgo de prueba
- El error reproducido en `status/deploy` fue: daemon Docker no disponible.
- Mensaje observado: `failed to connect to docker_engine`.

## Cambios aplicados

### Script robusto de deploy blue-green (PowerShell)
- Archivo: `scripts/deploy-bluegreen.ps1`
- Mejoras:
  - preflight de requisitos (docker, compose file, daemon, upstream activo),
  - creación automática de `deploy/active-upstream.conf` si falta,
  - logging persistente en `logs/deploy-bluegreen-*.log`,
  - rollback de switch de tráfico si falla cambio a color objetivo,
  - parámetros de robustez (`MaxAttempts`, `WaitSeconds`, `SkipBuild`, `NoRollback`),
  - manejo correcto de errores de comandos nativos en PowerShell 7.

### Deploy automático desde raíz
- Nuevo: `deploy.ps1`
- Nuevo: `deploy.bat`
- Ejecutables desde raíz para status/deploy/switch sin navegar a `scripts/`.

### Documentación
- Archivo: `README.md`
- Se documentaron comandos desde raíz y el uso de `./` en PowerShell.

## Validación ejecutada
- `./deploy.ps1 -Action status` -> now falla limpio con mensaje controlado cuando daemon está apagado.
- `./deploy.ps1 -Action deploy -SkipBuild` -> misma validación de preflight (sin falsas trazas largas).
- `./deploy.bat -Action status` -> requiere prefijo `./` en PowerShell, documentado.

## Acción operativa requerida
- Iniciar Docker Desktop/daemon antes del deploy.
- Luego ejecutar:
  - `./deploy.ps1 -Action deploy`
