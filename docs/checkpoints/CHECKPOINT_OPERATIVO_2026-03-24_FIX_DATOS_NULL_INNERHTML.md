# CHECKPOINT OPERATIVO 2026-03-24 - FIX DATOS NULL INNERHTML

## Contexto
Al ingresar a la sección Datos del frontend se mostraba:
`Cannot set properties of null (setting 'innerHTML')`.

La causa fue corrupción estructural de `web/index.html` en bloques de secciones:
- `datosSection` contenía etiquetas desbalanceadas y nodos ajenos.
- `databasesSection` mezclaba elementos de otras secciones (`usuarios`, `auditoria`).

## Cambios aplicados
Archivo modificado:
- `web/index.html`

Acciones:
1. Reconstrucción de `datosSection` con estructura válida.
2. Restitución de controles esperados por JS:
   - `datosOrderDir`
   - `tablasSelect` correctamente cerrado
   - botón `Consultar Uno` (`consultarUnDato()`)
3. Reconstrucción de `databasesSection` con IDs requeridos por `web/js/main.js`:
   - `databasesContainer`
   - `dbMaintenancePanel`
   - `maintenanceDatabaseSelect`
   - `dbMaintenanceResult`
   - `queryPanel`
   - `queryDatabase`
   - `querySQL`
   - `queryResult`
4. Eliminación de fragmentos contaminados de otras secciones dentro de `databasesSection`.

## Validación
- `pytest tests/test_sin_linea_e2e.py -q` -> **33 passed**.
- `pytest -q` -> **134 passed**.
- Revisión de errores editor:
  - `web/index.html`: sin errores.
  - `web/js/main.js`: sin errores.

## Resultado
Se elimina la condición de null en render de Datos y se restablece la integridad de las secciones de Datos/Bases de Datos en frontend.
