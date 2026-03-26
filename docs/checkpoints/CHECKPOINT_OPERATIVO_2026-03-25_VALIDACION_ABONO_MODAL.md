# CHECKPOINT OPERATIVO 2026-03-25 - Validación Visual de Abono en Modal

## Objetivo
Agregar validación visual en el modal de abono para prevenir capturas erróneas antes de enviar:
- marcar en rojo cuando el monto sea inválido o exceda saldo acumulado,
- bloquear el botón de registrar hasta que el monto sea válido.

## Cambios aplicados
- `web/js/main.js`
  - `showQuickAbonoModal(...)` ahora valida en vivo el monto.
  - Mensajes visuales:
    - error en rojo para monto inválido o mayor al saldo,
    - confirmación en verde cuando el monto es válido.
  - Botón `Registrar` queda deshabilitado mientras haya error.
  - Enter solo confirma cuando el monto ya es válido.
- `web/css/style.css`
  - Nuevos estilos para `qr-abono-feedback`, variantes `error/success` y estado disabled del botón.
- `tests/test_sin_linea_e2e.py`
  - Se amplían asserts de assets para validar presencia de feedback y bloqueo de submit.

## Validación ejecutada
- `c:/python314/python.exe -m pytest ../tests/test_sin_linea_e2e.py -k "qr_scan_abono_permite_monto_editable or css_modal_abono_es_responsive_en_movil"` -> 2 passed
- `c:/python314/python.exe -m pytest ../tests/test_sin_linea_e2e.py` -> 50 passed

## Resultado
El flujo de abono en móvil ahora previene montos fuera de rango con retroalimentación clara y reduce errores operativos antes de registrar pagos.
