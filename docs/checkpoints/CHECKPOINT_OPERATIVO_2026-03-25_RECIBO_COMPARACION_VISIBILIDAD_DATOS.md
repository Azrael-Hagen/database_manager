# CHECKPOINT OPERATIVO 2026-03-25 - Recibo: Comparacion Automatica y Visibilidad de Campos

## Objetivo
Corregir inconsistencia de recibos (abono aplicado y saldo acumulado) y aplicar flujo de comparacion previa con seleccion de campos visibles antes de imprimir.

## Cambios
### Backend
- `backend/app/api/qr.py`
  - Payload de recibo ahora persiste campos financieros completos:
    - `abono_aplicado`
    - `saldo_acumulado`
    - `deuda_total`
    - `total_abonado`
    - `estado_pago`
  - Registro y edicion de pagos inyectan esos datos al generar/actualizar recibo.

### Frontend
- `web/js/main.js`
  - Reimpresion por token ahora hidrata `abono`, `saldo`, `deuda`, `total abonado` desde payload persistido.
  - Antes de imprimir recibo individual o multiple:
    1. compara automaticamente con resumen actual del agente/semana.
    2. solicita al usuario que elija campos visibles del recibo.

### Pruebas
- `tests/test_sin_linea_e2e.py`
  - Nuevo caso E2E valida que recibo reimpreso incluye abono y saldo.

## Validacion
- Test puntual nuevo -> OK
- Test de edicion de recibo -> OK
- Suite `test_sin_linea_e2e.py` completa -> 44 passed

## Resultado
Recibos muestran correctamente datos financieros y el sistema ya obliga una etapa de control de visibilidad antes de imprimir.
