# CHECKPOINT OPERATIVO 2026-03-25 - Recibos: Edicion, Estado Abonado y Multiimpresion

## Objetivo
Atender mejoras en recibos de pago:
1. Permitir ajustar recibo al editar pago.
2. Mostrar estado Abonado en lugar de Al Corriente cuando es abono parcial.
3. Permitir imprimir varios recibos por hoja.

## Cambios aplicados
### Backend
- `backend/app/api/qr.py`
  - `PUT /api/qr/pagos/{pago_id}` ahora regenera/actualiza recibo persistido despues de editar pago.
  - Respuesta de edicion incluye bloque `recibo` con token/expiracion/linea.
  - `GET /api/qr/recibos` ahora incluye `pago_id` para habilitar accion de editar desde historico.

### Frontend
- `web/js/main.js`
  - Correccion de estado en comprobante al registrar pago: usa resultado real del backend.
  - Abono parcial ahora se etiqueta como Abonado.
  - Historico de recibos:
    - agrega seleccion multiple con checkbox.
    - agrega boton Imprimir seleccionados (varios por hoja).
    - agrega boton Editar por recibo (admin) usando `pago_id`.
  - Reimpresion por token respeta estado Abonado para pagos parciales.

### Pruebas
- `tests/test_sin_linea_e2e.py`
  - Nuevo caso E2E: editar pago refresca recibo para reimpresion.

## Validacion ejecutada
- `tests/test_sin_linea_e2e.py::TestDeudaManualE2E::test_editar_pago_refresca_recibo_para_reimpresion` -> OK
- `tests/test_sin_linea_e2e.py` -> 43 passed
- `tests/test_schema_updates.py` + `tests/test_reporte_conciliacion_automation.py` -> 9 passed

## Resultado
Se habilita flujo practico de edicion de recibos via edicion de pago, se corrige semantica de estado para abonos y se agrega impresion masiva por hoja en la vista de recibos.
