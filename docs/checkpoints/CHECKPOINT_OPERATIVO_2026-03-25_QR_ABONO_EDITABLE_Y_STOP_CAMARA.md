# CHECKPOINT OPERATIVO 2026-03-25 - QR: Abono Editable y Stop Inmediato de Cámara

## Objetivo
Corregir el flujo operativo en Escaneo QR para:
1) Permitir registrar abono parcial con monto editable.
2) Detener la cámara inmediatamente al obtener un resultado.

## Cambios aplicados
- `web/js/main.js`
  - `registrarPagoDesdeEscaneo('abono')` ahora solicita monto editable con `showAppPrompt`.
  - El payload de abono rápido usa `pagado: false` para no forzar liquidación completa por default.
  - `manejarQRLeido` detiene el escáner en cuanto detecta un código válido para evitar lecturas repetidas.
  - `detenerEscanerQR` ahora también restablece el botón de cámara a estado "Iniciar Cámara".
- `web/js/qrCobros.js`
  - `qrToggleCamera` sincroniza el estado interno con el estado real del escáner para evitar dobles clics tras auto-stop.
- `tests/test_sin_linea_e2e.py`
  - Se agregaron validaciones de assets para asegurar:
    - presencia de stop inmediato al leer QR,
    - flujo de abono con monto editable en escaneo.

## Validación ejecutada
- `c:/python314/python.exe -m pytest ../tests/test_sin_linea_e2e.py -k "qr_scan_tiene_continuidad_y_antirebote or qr_scan_abono_permite_monto_editable or qr_toggle_camera_espera_inicio_real"` -> 3 passed
- `c:/python314/python.exe -m pytest ../tests/test_sin_linea_e2e.py` -> 49 passed

## Resultado
El operador puede capturar abonos parciales con monto editable desde escaneo QR y la cámara se detiene inmediatamente al primer resultado, evitando dobles lecturas y confusión operativa.
