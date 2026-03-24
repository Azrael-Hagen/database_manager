# CHECKPOINT TECNICO - 2026-03-23 - AJUSTE MANUAL DE DEUDA UI + E2E

## Cambios implementados
- Se agrega soporte backend para ajuste manual de deuda por agente persistido en configuracion:
  - `DEUDA_AJUSTE_MANUAL_AGENTE_<id>`.
- El resumen de cobranza ahora expone:
  - `deuda_base_total`
  - `ajuste_manual_deuda`
  - `deuda_total` (con ajuste aplicado)
- Endpoints nuevos:
  - `GET /api/qr/agentes/{agente_id}/deuda-manual`
  - `PUT /api/qr/agentes/{agente_id}/deuda-manual`
- UI nueva en seccion QR y Cobros:
  - Panel "Control Manual de Deuda" con consultar/aplicar/limpiar.
  - Modos: `saldo_objetivo` y `ajuste`.
- Verificacion QR y resumen de pagos muestran deuda base y ajuste manual para coherencia operativa.

## Validacion
- Prueba focalizada frontend/assets y wiring:
  - `c:/python314/python.exe -m pytest -q tests/test_sin_linea_e2e.py -k "FrontendAssets or lineas"`
  - Resultado: `6 passed`
- Prueba E2E del control manual de deuda:
  - `c:/python314/python.exe -m pytest -q tests/test_sin_linea_e2e.py -k "DeudaManualE2E or deuda and manual" -vv -s`
  - Resultado: `1 passed`
- Suite completa:
  - `c:/python314/python.exe -m pytest -q`
  - Resultado: `46 passed`

## Resultado operativo
El ajuste manual de deuda ya es visible, editable y verificable en la UI, con impacto real en los calculos del backend y consistencia end-to-end.
