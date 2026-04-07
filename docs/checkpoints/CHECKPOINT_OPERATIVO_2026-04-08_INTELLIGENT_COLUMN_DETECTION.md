# Checkpoint Operativo — 2026-04-08 — Detección Inteligente de Columnas rev11

## Estado General
- **Commit**: 3cbe6d1 + 7b7ddfd (main / origin/main)
- **Revisión**: 1.5.0-rev11
- **Tests**: 55 passed (test_smart_import.py) — 0 failed

---

## Cambios Implementados

### Nuevo módulo: `backend/app/importers/column_detector.py`
Motor de detección avanzada (sin dependencias nuevas, solo stdlib + pandas):

| Función | Propósito |
|---|---|
| `detect_header_row(df, max_scan=10)` | Escanea las primeras 10 filas del DataFrame crudo y devuelve el índice 0-based de la fila más probable como cabecera real. Cambia de fila 0 solo cuando la mejor candidata puntúa >1.5× la fila 0. |
| `infer_from_values(sample_values)` | 14 reglas regex para inferir campo canónico a partir de valores (email, teléfono MX, IMEI, deuda $NNN, ubicación, nombre propio, alias). |
| `detect_table_regions(df)` | Detecta múltiples tablas separadas por filas vacías. Devuelve lista de `{inicio_fila, fin_fila}` (1-based). |
| `ProfileStore` | Caché JSON en `mapping_profiles.json`, clave SHA-1[:16] de cabeceras normalizadas. `lookup(headers)` y `save(headers, mapping)`. |
| `suggest_mapping_advanced(...)` | 6 niveles de decisión: perfil_guardado → cabecera+valor_coinciden → cabecera_dominante → valor_patron → blend_débil → desconocido. Incluye campo `evidencia`. |

### `backend/app/importers/smart_importer.py`
- Import de `column_detector` al inicio.
- `FIELD_SYNONYMS`: agregados `fcc`, `imei`, `deuda`; extendidos `fp`, `fc`, `ubicacion`, `telefono` con variantes con punto.
- `_parse_file_to_rows`: ahora acepta `header: int = 0`; pasa `header=N` a `pd.read_excel` y salta N líneas en CSV.
- `analyze_file`: nuevo param `header_fila=-1`; auto-detecta con `detect_header_row`; llama `detect_table_regions`; samplea 20 valores/columna; usa `suggest_mapping_advanced`; devuelve `detected_header_row` y `tabla_regiones`.
- `preview_import`: nuevo param `header_fila=0`; pasa a `_parse_file_to_rows`.

### `backend/app/api/smart_import.py`
- Import de `get_profile_store`.
- `_parse_rows`: acepta `header=0`.
- Endpoint `/analyze`: acepta `header_fila: int = Form(-1)`.
- Endpoint `/preview`: acepta `header_fila: int = Form(0)`.
- Endpoint `/execute`: acepta `header_fila: int = Form(0)`; guarda perfil en `ProfileStore` tras importación exitosa (inserted+updated > 0).

### `web/js/smartImport.js`
- `CANONICAL_FIELDS`: añadidos `fcc`, `imei`, `deuda`, `extension`.
- Después de analyze: muestra "fila de encabezado detectada: N" si N>0.
- `_siRenderStep1Results`: info de fila detectada, alerta de múltiples tablas, columna Evidencia, badge por tipo (`valor_patron`=morado, `perfil_guardado`=teal, `combinado`=azul).
- `formData` de preview y execute ahora incluyen `header_fila`.

### `tests/test_smart_import.py`
- Helper módulo-nivel `_make_category_header_excel()`.
- Clase `TestColumnDetector` (14 tests): infer_from_values ×6, detect_header_row ×2, suggest_mapping_advanced ×3, ProfileStore ×3, integración analyze_file ×2.

---

## Flujo de Funcionamiento

```
Upload Excel con fila 0 = etiqueta de categoría ("CONCHA / EMPRESA DEMO")
    ↓
analyze_file(header_fila=-1)
    ↓ pandas lee con header=None (crudo)
    ↓ detect_header_row → devuelve 1 (fila ALIAS/NOMBRE/F.P/IMEI/DEUDA)
    ↓ re-lee con header=1
    ↓ profile lookup por SHA-1 de cabeceras
    ↓ samplea 20 valores por columna
    ↓ suggest_mapping_advanced por columna
        → ALIAS → alias (exacta, 0.98)
        → NOMBRE COMPLETO → nombre (sinonimo, 0.85)
        → EXTENSION → telefono (fuzzy, 0.70)
        → F.P → fp (exacta tras normalización, 0.90)
        → F.C. → fc (exacta, 0.90)
        → F.C.C. → fcc (exacta, 0.88)
        → IMEI → imei (exacta, 0.98) + valor_patron (0.91)
        → DEUDA → deuda (exacta) + valor_patron $NNN (0.94)
    ↓ devuelve detected_header_row=1, columnas con evidencia
    ↓
UI muestra: "ℹ️ Fila de encabezado detectada automáticamente: fila 2"
            tabla con badges de evidencia por columna
    ↓
preview/execute reciben header_fila=1 → leen correctamente desde la fila de datos
    ↓
execute exitoso → ProfileStore.save(cabeceras, mapeo) → aprendizaje persistido
```

---

## Archivos Implicados
| Archivo | Estado |
|---|---|
| `backend/app/importers/column_detector.py` | **Nuevo** |
| `backend/app/importers/mapping_profiles.json` | **Nuevo** (caché vacío inicial) |
| `backend/app/importers/smart_importer.py` | Modificado |
| `backend/app/api/smart_import.py` | Modificado |
| `web/js/smartImport.js` | Modificado |
| `tests/test_smart_import.py` | Modificado (+14 tests) |
| `deploy/version-info.json` | rev11 |
| `deploy/CHANGELOG.server.md` | Entrada rev11 |
| `backend/app/versioning.py` | DEFAULT rev11 |
