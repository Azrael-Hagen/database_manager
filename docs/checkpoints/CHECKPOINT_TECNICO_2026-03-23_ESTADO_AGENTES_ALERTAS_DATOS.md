# CHECKPOINT TECNICO - 2026-03-23 (Estado de Agentes, Alertas y Datos)

## Objetivo
Corregir vacíos funcionales detectados en operación:
- Estado de Agentes vacío / sin coherencia de navegación.
- Cobro sin validación estricta de línea activa.
- Generación masiva de QR no funcional en UI.
- Alertas de sistema sin entrega consistente a usuarios activos.
- Edición y eliminación en Datos confusa/fallida en contextos espejo.
- Remover campo innecesario de "Teléfono esperado" en Generar QR.

## Cambios aplicados
1. Frontend navegación/roles:
- Unificación `estadoAgentes` (antes mezclado con `sinLinea`).
- Corregidos IDs/section routing en `main.js` y `index.html`.

2. Estado de Agentes:
- UI ahora consume `/api/qr/agentes/estado`.
- Backend `/agentes/estado` ahora lista todos los agentes activos con `linea_estado` (`ASIGNADA`/`SIN_LINEA`).
- Banner superior calcula conteo de `SIN_LINEA`.

3. Cobros:
- Backend `/api/qr/pagos` ahora rechaza cobro si el agente no tiene línea activa asignada.

4. QR masivo:
- Corregido wiring de botones/resultados para que use funciones/IDs correctos.

5. Generar QR:
- Eliminado campo "Teléfono esperado" del formulario.
- Verificación se basa en ID/voip/semana, no en teléfono esperado manual.

6. Alertas del sistema:
- Backend `alertas.py`: envío/desactivación permitido a `super_admin` autenticado (sin bloqueo por máquina).
- Listado/lectura de alertas habilitado para cualquier usuario autenticado.
- Frontend adapta contrato (`items`, `remitente_username`).
- Añadido polling periódico y badge en menú para usuarios activos.

7. Sección Datos (editar/eliminar):
- Acciones de edición/eliminación solo en `database_manager.datos_importados`.
- En espejos de solo lectura se muestra mensaje explícito.
- Fallback por UUID si el ID no coincide al editar/eliminar.
- Edición ahora permite actualizar `es_activo`.

8. Schemas:
- `DatoImportadoActualizar` acepta `es_activo`.

## Riesgos controlados
- Se evita operar sobre vistas/espejos no editables.
- Se evita registrar pagos de agentes sin línea real activa.
- Se mejora consistencia entre backend/frontend sin cambiar flujo validado de autenticación.

## Verificación pendiente
- Pruebas de integración puntuales de endpoints y flujo UI en sesión real.
