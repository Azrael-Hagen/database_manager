# CHECKPOINT OPERATIVO 2026-03-22 - QR Estatus Actual + Nombres Logicos

## Objetivo
1. Al abrir QR del agente desde servidor, mostrar estatus actual completo:
- linea asignada o no
- deuda total, total abonado, saldo acumulado, semanas pendientes
- estado de pago semanal
2. Facilitar registro de pago desde el QR individual.
3. Hacer entendibles tablas/vistas para usuarios no avanzados, mostrando nombre logico y para que sirve.

## Cambios aplicados

### Backend QR / estatus
Archivo: `backend/app/api/qr.py`
- Se mejoro `_render_public_status_page(...)` para mostrar:
  - linea activa
  - monto semana
  - total abonado
  - deuda total
  - saldo acumulado
  - semanas pendientes
  - boton/enlace de accion para ir al flujo de pago
- Se corrigio URL fallback del QR por UUID:
  - de `/api/qr/public/verify-uuid/{uuid}` a `/api/qr/public/verify/{uuid}`
- Se mantuvo compatibilidad agregando alias de ruta:
  - `GET /api/qr/public/verify-uuid/{uuid}`
- Endpoints publicos ahora incluyen resumen acumulado y enlace de pago interno:
  - `verify-secure`
  - `verify/{uuid}`
  - `verify-by-id/{agente_id}`

### Frontend deep-link pago desde QR
Archivo: `web/js/main.js`
- Se agrego manejo de query params de arranque:
  - `section=qr`
  - `agente_id`
  - `semana`
  - `autoverify=1`
- Al abrir enlace desde QR y autenticar, la app:
  - navega a seccion QR
  - precarga agente/semana
  - ejecuta verificacion y resumen de pago automaticamente

### Nombres logicos para tablas y vistas
Archivo: `web/js/main.js`
- Se agrego catalogo `DB_OBJECT_CATALOG` (nombre fisico -> nombre logico + proposito).
- Se aplica en:
  - selector de tablas en seccion Datos
  - listado de Tablas en seccion Bases de Datos
  - listado de Vistas en seccion Bases de Datos
  - encabezado de vista de datos de tabla/vista

## Verificacion final
- Sin errores de analisis en:
  - `backend/app/api/qr.py`
  - `web/js/main.js`
- Compilacion backend OK:
  - `py_compile app/api/qr.py app/utils/pagos.py app/schemas.py`
- Vistas espejo en `registro_agentes` siguen disponibles:
  - `vw_dm_agentes_operacion_actual`
  - `vw_dm_control_sync_agentes`
  - `vw_dm_cat_estatus_agente`

## Nota de datos actuales
En esta corrida no hay agentes activos en la base canonica, por eso no se pudo demostrar QR real con un agente existente. La logica queda activa para el siguiente agente operativo.
