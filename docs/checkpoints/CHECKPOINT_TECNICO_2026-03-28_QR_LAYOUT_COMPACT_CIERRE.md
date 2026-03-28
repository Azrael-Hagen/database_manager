# CHECKPOINT TECNICO — 2026-03-28 — QR Layout Compact (CIERRE)

## Cambios implementados
- Backend (`backend/app/utils/qr_print.py`):
  - `sheet` paso de 27 a 30 QR por pagina (3x10).
  - `oficio` paso de 27 a 30 QR por pagina (3x10).
  - Se agrego soporte de overrides enteros para `rows` y `columns`.
  - `cell_w` y `cell_h` ahora se recalculan automaticamente desde pagina/margenes/rows/columns cuando no se fuerzan explicito, reduciendo espacio muerto.
- Frontend (`web/js/main.js` + `web/index.html`):
  - Se retiro editor numerico complejo.
  - Se implemento selector de perfiles de densidad por layout (estandar/compacto).
  - Persistencia simplificada en `localStorage` por perfil seleccionado.
  - Textos de layout actualizados a 30 QR para carta/oficio.
- Pruebas nuevas (`tests/test_qr_print_layout.py`):
  - Validan rows/columns override.
  - Validan recomputo de celdas.
  - Validan preservacion de `cell_h` explicito.
  - Validan clamps de limites e ignorar tipos invalidos.

## Validacion ejecutada
- `pytest tests/test_qr_print_layout.py` -> `4 passed`.
- Intento de prueba E2E de export PDF:
  - `pytest tests/test_sin_linea_e2e.py::TestQrStaticoYExportacion::test_exportacion_pdf_por_lotes`
  - Bloqueado por dependencia faltante en entorno actual: `ModuleNotFoundError: No module named 'fastapi'`.

## Riesgos remanentes
- La validacion E2E completa de endpoint PDF en este entorno no pudo cerrarse por faltante de dependencias.
- Perfiles compactos de alta densidad pueden requerir ajuste fino visual segun impresora/papel real.

## Estado
- Bloque funcional implementado y pruebas unitarias en verde.
- Pendiente validacion E2E completa cuando el entorno tenga dependencias backend disponibles.
