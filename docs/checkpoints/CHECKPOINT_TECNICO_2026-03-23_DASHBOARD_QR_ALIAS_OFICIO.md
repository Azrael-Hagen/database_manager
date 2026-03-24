# CHECKPOINT TECNICO 2026-03-23 - DASHBOARD + EXPORT QR (ID/ALIAS + OFICIO)

## Objetivo
Alinear la experiencia operativa con los cambios recientes:
- Etiquetas QR minimalistas (solo ID y alias).
- Acceso directo desde Dashboard a exportacion QR por lotes.
- Soporte de hoja tamano oficio en exportacion PDF.
- KPIs de Dashboard alineados al estado actual de lineas y agentes sin linea.

## Cambios aplicados

### Backend
- `backend/app/api/qr.py`
  - Endpoint `GET /api/qr/agentes/export/pdf` ahora acepta `layout=oficio`.
  - Se incluye `alias` en `export_rows` (tomado de `datos_adicionales.alias`).
- `backend/app/utils/qr_print.py`
  - Nuevo layout `oficio` (8.5x13).
  - Etiqueta simplificada: solo `ID | alias`.
  - Se removio bloque extra de telefono/linea/estado en la etiqueta.

### Frontend
- `web/index.html`
  - En `qrExportLayout` se agrego opcion `Hoja oficio`.
  - Se agregaron IDs para salto directo a exportacion (`qrExportSectionTitle`, `qrExportCard`).
  - En Dashboard:
    - Nuevas tarjetas KPI: `Agentes Sin Línea`, `Líneas Activas`, `Líneas Asignadas`.
    - Nueva accion rapida: `Exportación QR`.
- `web/js/main.js`
  - `loadDashboardData` ahora llena los nuevos KPIs con:
    - `totals.sin_linea`
    - `totals.lineas_activas`
    - `totals.lineas_asignadas_activas`
  - Nueva funcion `irAExportacionQRLotes()` para abrir seccion QR y desplazar a la tarjeta de exportacion.

### Tests
- `tests/test_sin_linea_e2e.py`
  - `test_exportacion_pdf_por_lotes` ahora valida tambien `layout=oficio`.
  - `test_index_tiene_controles` valida presencia de opcion `oficio` en frontend.

## Validacion ejecutada
- `./.venv/Scripts/python.exe -m pytest tests/test_sin_linea_e2e.py -k "exportacion_pdf_por_lotes or test_index_tiene_controles or test_js_tiene_funciones" -q`
  - Resultado: 3 passed

## Resultado
Se mantiene sincronizacion UI-BD/API: el dashboard refleja metrica operativa actual y la exportacion QR ya soporta hoja oficio con etiqueta reducida a ID+alias, como requerido.
