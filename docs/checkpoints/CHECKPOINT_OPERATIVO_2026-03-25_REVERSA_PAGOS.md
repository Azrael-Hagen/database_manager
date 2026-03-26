# CHECKPOINT OPERATIVO 2026-03-25 - Reversa de Pagos/Abonos

## Objetivo
Permitir cancelar y revertir abonos/pagos registrados por error (por ejemplo pruebas), con flujo sencillo para operación y trazabilidad en backend.

## Cambios aplicados
- Backend:
  - Nuevo endpoint administrativo `POST /api/qr/pagos/{pago_id}/revertir`.
  - Reversa total del pago: monto a 0, pagado en falso y fecha_pago en null.
  - Registro auditable en `cobros_movimientos` con tipo `REVERSA_PAGO` y motivo.
  - Recibo persistido se actualiza con estado `Cancelado` y bandera `revertido`.
- Frontend:
  - Botón `Revertir` desde reporte semanal y desde recibos guardados.
  - Confirmación explícita + captura de motivo opcional.
  - Recarga automática de reporte, recibos y resumen del agente tras revertir.
- Cliente API:
  - Método `revertirPagoSemanalAdmin`.

## Archivos modificados
- `backend/app/schemas.py`
- `backend/app/api/qr.py`
- `web/js/api-client.js`
- `web/js/main.js`
- `tests/test_sin_linea_e2e.py`

## Pruebas
- Nuevo E2E:
  - Revertir pago actualiza recibo y estado.
  - Intentar revertir dos veces (pago ya en cero) devuelve conflicto.

## Validación ejecutada
- `c:/python314/python.exe -m pytest ../tests/test_sin_linea_e2e.py -k "revertir_pago or reversion"` -> 2 passed
- `c:/python314/python.exe -m pytest ../tests/test_sin_linea_e2e.py` -> 48 passed

## Resultado
La operación ya puede cancelar/revertir pagos de forma clara y segura, manteniendo consistencia UI-BD y trazabilidad operativa.
