# CHECKPOINT BASE - 2026-03-22 (CIERRE LIMPIO)

## Objetivo del corte
Establecer una base limpia, estable y lista para futuros updates, con control de cambios recientes, seguridad de borrados, soporte HTTPS/TLS y depuración de artefactos no funcionales.

## Estado funcional consolidado

### 1) Roles y seguridad
- Jerarquía activa:
  - viewer
  - capture
  - admin
  - super_admin
- `super_admin` integrado en validación de token, rank de permisos y guards dedicados.
- Endpoints críticos de borrado permanente/purga restringidos a `super_admin`.

### 2) Flujo de borrados con respaldo y rollback
- Antes de borrar (soft/hard), se guarda snapshot del registro en `papelera_registros`.
- `DELETE /api/datos/{id}`:
  - soft delete
  - deja respaldo en papelera
- `DELETE /api/datos/{id}/hard-delete`:
  - solo super_admin
  - respaldo previo + eliminación definitiva
- `DELETE /api/datos/purge/inactivos`:
  - solo super_admin
- Nuevos endpoints:
  - `GET /api/datos/papelera`
  - `POST /api/datos/{id}/rollback`

### 3) UI/UX de seguridad operativa
- Doble confirmación para operaciones de borrado:
  - confirm inicial
  - confirmación por texto `CONFIRMAR`
- Funciones de hard delete/rollback ocultas para roles no autorizados.
- Mensajes de notificación alineados con el respaldo automático.

### 4) Cámara QR y compatibilidad de dispositivos
- Flujo de escaneo mejorado:
  - solicitud explícita de permiso cámara
  - detección por lista de cámaras
  - fallback por constraints
  - selector manual en fallo
- Manejo explícito de bloqueo por contexto inseguro (HTTP sin permisos de media).

### 5) HTTPS/TLS local para cámara en red
- Script agregado: `scripts/setup-https.ps1`.
- Certificados locales generados con mkcert en `ssl/cert.pem` y `ssl/key.pem`.
- Portproxy activo:
  - 443 -> 127.0.0.1:8443
- Backend actualizado para levantar HTTPS en paralelo cuando existen certificados.
- `.env` y CORS ajustados para soporte HTTPS local.

## Depuración y limpieza aplicada

### Limpieza técnica realizada
- Eliminado entorno duplicado `backend/venv`.
- Eliminadas carpetas `__pycache__` del árbol de código local.
- Reubicados checkpoints históricos de raíz a `docs/checkpoints/`.
- Movidos respaldos SQL desde `tmp/chosen_backups` a `backend/backups/manual/`.
- Ajustado `.gitignore` para prevenir ruido futuro:
  - `tmp/`
  - `ssl/*.pem`
  - `ssl/*.key`

### Observaciones de limpieza
- Un archivo de log activo puede permanecer bloqueado por proceso en ejecución.
  - Esto no afecta la funcionalidad.
  - Se limpia al detener proceso/servicio y volver a ejecutar limpieza.

## Estado de base para siguientes updates
- Punto de partida recomendado: este checkpoint.
- Convención: toda mejora nueva debe registrarse desde este corte para evitar dispersión de históricos en raíz.
- Recomendación operativa: mantener checkpoints bajo `docs/checkpoints/`.

## Verificación rápida sugerida post-corte
1. Levantar servidor.
2. Probar acceso en `https://phantom.database.local`.
3. Validar login por rol (`admin`, `super_admin`).
4. Probar soft delete, hard delete y rollback.
5. Validar escaneo QR desde cámara en red.

## Archivos clave del corte
- `backend/main.py`
- `backend/app/security.py`
- `backend/app/models.py`
- `backend/app/database/orm.py`
- `backend/app/api/datos.py`
- `web/js/main.js`
- `web/js/api-client.js`
- `scripts/setup-https.ps1`
- `.gitignore`
