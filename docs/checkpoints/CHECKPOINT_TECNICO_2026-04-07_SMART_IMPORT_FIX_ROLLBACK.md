# CHECKPOINT TECNICO — 2026-04-07 — Smart Import fix + rollback

## Objetivo
Restaurar operatividad completa del importador inteligente, asegurar visibilidad de comparaciones (cambios detectados) y habilitar rollback transaccional opcional en ejecucion.

## Alcance
- web/js/smartImport.js
- web/index.html
- backend/app/api/smart_import.py
- tests/test_smart_import.py
- tests/test_sin_linea_e2e.py

## Riesgos
1. Rotura de tabs en UI de importacion por IDs/valores inconsistentes.
2. Commits parciales en DB cuando hay errores por fila.
3. Regresiones en execute/preview existentes.

## Mitigacion
- Agregar pruebas de wiring UI y de rollback en endpoint.
- Mantener compatibilidad con modos actuales (insertar/actualizar/upsert).
- Rollback opcional activado solo por bandera explicita.

## Criterios de salida
- Tab inteligente visible y funcional.
- Preview muestra comparacion de campos actual->nuevo.
- Execute soporta rollback opcional si hay errores.
- Pruebas smart import y UI en verde.

## Ejecucion y hallazgos
- Causa principal encontrada: el tab inteligente no estaba bien cableado (funcion esperaba valores/IDs distintos a los definidos en HTML), provocando flujo aparente "deshabilitado" o roto.
- Se corrigio `smartImportSetTab` para soportar `smart`/`intelligent` y usar IDs reales (`siTabClassicBtn`, `siTabSmartBtn`, `importClassicTab`, `importSmartTab`).
- Se mejoro preview para mostrar detalle de comparacion por campo (`actual -> nuevo`) en filas actualizables.
- Se agrego opcion de rollback en UI y API (`rollback_si_hay_errores`) para revertir toda la transaccion cuando hay errores por fila.

## Validacion
- `PYTHONPATH=backend python -m pytest tests/test_smart_import.py -q` -> 37 passed.
- `PYTHONPATH=backend python -m pytest tests/test_smart_import.py::TestSmartImportEndpoints::test_execute_rollback_on_error_reverts_changes tests/test_sin_linea_e2e.py::TestFrontendAssets::test_smart_import_ui_tabs_y_rollback_wiring -q` -> 2 passed.
