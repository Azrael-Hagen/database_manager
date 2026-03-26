# CHECKPOINT OPERATIVO 2026-03-25 - Modal de Abono Optimizado para Móvil

## Objetivo
Mejorar el flujo de registro de abono desde Escaneo QR para pantallas pequeñas con una interfaz clara y editable.

## Cambios aplicados
- `web/js/main.js`
  - Nuevo helper `showQuickAbonoModal(...)` para capturar monto de abono en modal visual.
  - El modal muestra: monto sugerido, saldo actual y cuota semanal.
  - Incluye botones rápidos: usar cuota, usar saldo, sugerido.
  - `registrarPagoDesdeEscaneo('abono')` usa este modal en lugar de prompt plano.
- `web/css/style.css`
  - Nuevos estilos para `qr-abono-modal`, KPIs y acciones.
  - Ajustes responsive en móvil (`max-width: 768px`) para layout vertical y botones más accesibles.
- `tests/test_sin_linea_e2e.py`
  - Nuevas validaciones de assets para modal de abono y estilos responsive.

## Validación ejecutada
- `c:/python314/python.exe -m pytest ../tests/test_sin_linea_e2e.py -k "qr_scan_abono_permite_monto_editable or css_modal_abono_es_responsive_en_movil or qr_scan_tiene_continuidad_y_antirebote"` -> 3 passed
- `c:/python314/python.exe -m pytest ../tests/test_sin_linea_e2e.py` -> 50 passed

## Resultado
El operador en celular ahora tiene un modal claro y táctil para registrar abonos parciales con mejor legibilidad y menor error de captura.
