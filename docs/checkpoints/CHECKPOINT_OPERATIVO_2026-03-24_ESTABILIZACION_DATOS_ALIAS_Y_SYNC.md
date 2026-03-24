# CHECKPOINT OPERATIVO 2026-03-24 - ESTABILIZACION DATOS, ALIAS Y SYNC

## Contexto
Se detecto error de guardado en UI (Cambios y Bajas) y se solicito priorizar alias en UI, revisar coherencia de flujo de datos y redundancias.

## Hallazgos clave
- El endpoint de actualizacion de agentes podia fallar por dependencias auxiliares (sync con legado y auditoria), devolviendo 500 aunque la operacion principal en database_manager era valida.
- Existia acoplamiento fuerte CRUD -> sync legado (registro_agentes), lo que incrementaba errores operativos cuando legado estaba incompleto/no disponible.
- En listados de gestion de agentes se seguia mostrando columna Nombre aunque el flujo operativo prioriza Alias.

## Cambios aplicados
Archivos modificados:
- backend/app/api/datos.py
- web/js/main.js
- tests/test_api.py

### 1) Robustez CRUD en base canonica
- Se agregaron helpers:
  - _try_sync_legacy_agente(...)
  - _try_registrar_auditoria(...)
- La sincronizacion legacy y auditoria pasan a modo best-effort con logging.
- Si falla legado/auditoria, NO se rompe la operacion principal sobre datos_importados.

### 2) Prioridad visual de alias en UI de gestion
- En render de Gestion de Agentes se elimino la columna Nombre del listado.
- Se mantiene Alias como campo principal visible.
- Nombre queda para consulta/edicion directa del agente.

### 3) TDD de regresion
- Se agrego suite TestDatosRobustezUpdate para validar:
  - actualizar dato no falla si cae sync legacy
  - actualizar dato no falla si cae auditoria

## Validacion
- Pruebas nuevas: 2/2 passed.
- Suite completa: 138 passed.

## Resultado
- Se elimina el error operativo de guardado por subsistemas auxiliares.
- Se mantiene database_manager como fuente canonica.
- UI de gestion alineada a prioridad de alias.
