# CHECKPOINT OPERATIVO 2026-03-24 - FIX QR SCAN AUTOLECTURA

## Contexto
En la sección de Escaneo QR no se estaba logrando una lectura automática confiable al pasar códigos frente a la cámara.

Riesgos detectados en frontend:
- El escáner se detenía después de cada lectura (`manejarQRLeido` invocaba `detenerEscanerQR`).
- El botón de cámara quedaba en estado "encendido" aunque el inicio real de la cámara fallara.
- Al salir de la sección `qrScan`, la cámara podía quedar activa y generar estado inconsistente al regresar.

## Cambios aplicados
Archivos modificados:
- `web/js/main.js`
- `web/js/qrCobros.js`
- `tests/test_sin_linea_e2e.py`

### main.js
1. Escaneo continuo y anti-duplicados:
   - `QR_SCAN_DUPLICATE_WINDOW_MS`
   - `qrLastDecodedText`, `qrLastDecodedAtMs`
   - `qrDecodeInFlight`
2. `manejarQRLeido(decodedText)`:
   - Ya no detiene el escáner al leer.
   - Ignora lecturas duplicadas en ventana corta.
   - Bloquea reentrada mientras se procesa una verificación.
3. Estado de escáner:
   - nueva función `isQrScannerRunning()`.
4. Limpieza al navegar:
   - al salir de `qrScan`, se invoca `detenerEscanerQR()` de forma segura.

### qrCobros.js
1. `qrToggleCamera()` ahora es async y espera resultado real de inicio/parada.
2. El estado visual del botón se actualiza en base a `window.isQrScannerRunning()`.
3. El wrapper de `detenerEscanerQR` espera su promesa antes de resetear el toggle.

### tests (TDD)
Se agregaron pruebas de assets para blindar la mejora:
- continuidad + anti-rebote en scanner
- toggle de cámara dependiente de inicio real

## Validación
- TDD red: 2 pruebas nuevas fallando inicialmente (esperado).
- TDD green: 2/2 pruebas nuevas pasando.
- Suite `tests/test_sin_linea_e2e.py`: 35 passed.
- Suite completa: 136 passed.

## Resultado
El escaneo QR queda en modo de lectura continua, con control anti-duplicados y sincronía correcta entre estado real de cámara y UI.
