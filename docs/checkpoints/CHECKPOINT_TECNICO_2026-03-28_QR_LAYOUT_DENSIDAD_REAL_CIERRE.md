# CHECKPOINT TECNICO — 2026-03-28 — QR Layout Densidad Real (CIERRE)

## Ajustes aplicados
- `backend/app/utils/qr_print.py`
  - `sheet`: 4x9 => 36 QR/pagina (antes 30).
  - `oficio`: 4x10 => 40 QR/pagina (antes 30).
  - Se redujeron margenes y separacion lateral para aumentar ocupacion real de hoja.
  - Se corrigio render interno para que la caja de contenido use casi todo el ancho de etiqueta (elimina franjas laterales en blanco observadas en evidencia).
- `web/js/main.js`
  - Presets actualizados a densidad real:
    - Carta estandar: 36, compacto: 40.
    - Oficio estandar: 40, compacto: 44.
- `web/index.html`
  - Etiquetas de selector actualizadas con conteos base nuevos.
- `tests/test_qr_print_layout.py`
  - Nuevas pruebas para defaults: `sheet` 4x9 y `oficio` 4x10.

## Validacion ejecutada
Comando:
- `$env:PYTHONPATH='backend'; c:/python314/python.exe -m pytest tests/test_qr_print_layout.py tests/test_sin_linea_e2e.py::TestQrStaticoYExportacion::test_exportacion_pdf_por_lotes`

Resultado:
- `7 passed` (incluye E2E real de `/api/qr/agentes/export/pdf`).

## Estado
- COMpletado: densidad y ocupacion visual corregidas segun evidencia de PDF.
