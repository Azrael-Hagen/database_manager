# Checkpoint Operativo - 2026-03-24 - Cierre de fallos de pruebas

## Objetivo
Cerrar fallos de la suite completa de pruebas sin romper funcionalidad validada.

## Problema raiz detectado
Los tests compartian una sola instancia global de FastAPI (`main.app`) y sobrescribian `app.dependency_overrides[get_db]` entre modulos, provocando contaminacion cruzada de base de datos en memoria y resultados no deterministas.

## Correcciones aplicadas
- `tests/test_sin_linea_e2e.py`:
  - Se agrego `_bind_test_db_override()`.
  - Se fuerza override local en `_db()` y `_clear_agent_tables()`.
- `tests/test_smart_export.py`:
  - Se agrego fixture autouse `_bind_smart_export_db_override` para re-aplicar override por prueba.
- `tests/test_smart_import.py`:
  - Se agrego fixture autouse `_bind_smart_import_db_override` para re-aplicar override por prueba.

## Validacion
- `pytest tests/test_sin_linea_e2e.py -q` -> 33 passed
- `pytest tests/test_smart_export.py -q` -> 32 passed
- `pytest tests/test_smart_import.py -q` -> 33 passed
- `pytest -q` -> 134 passed

## Estado
Suite completa en verde. Se mantienen warnings de deprecacion no bloqueantes para bloque posterior de hardening.
