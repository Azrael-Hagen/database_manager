# Checkpoint Operativo 2026-03-24 - Fix Estado Pago y Guardado Cambios

## Contexto
Reporte activo del usuario:
1. Agentes con saldo pendiente no aparecen correctamente como pendientes.
2. Error 500 al guardar cambios en seccion Cambios y Bajas.

## Diagnostico confirmado
- Se reprodujo 500 en PUT /api/datos/{id}.
- Log backend confirma validacion de respuesta:
  - response.datos_adicionales espera dict
  - se devuelve string JSON, provocando error interno.

## Riesgos
- Inconsistencia de estado de pago por uso de flag pagado en lugar de saldo real.
- Regresion en UI si backend cambia formato de estado sin ajuste en render.

## Plan de correccion
1. Agregar pruebas de regresion (TDD):
   - update de dato con datos_adicionales debe responder 200 y objeto.
   - estado-pago debe marcar pendiente cuando hay saldo acumulado > 0.
2. Ajustar backend:
   - normalizar datos_adicionales en respuesta CRUD /api/datos.
   - calcular estado_pago y pagado en /api/qr/agentes/estado-pago basado en saldo real.
3. Ajustar UI:
   - render de estado pago en tabla operativa con prioridad a saldo_acumulado.
4. Ejecutar pruebas objetivo + suite completa.

## Alcance
- Sin cambios de schema.
- Sin cambios en funcionalidades validadas fuera de estado visual y serializacion de respuesta.
