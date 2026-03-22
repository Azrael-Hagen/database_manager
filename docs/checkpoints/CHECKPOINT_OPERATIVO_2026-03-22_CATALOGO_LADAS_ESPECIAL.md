# Checkpoint Operativo - Integracion Catalogo Ladas Especial

Fecha: 2026-03-22

## Objetivo
Integrar la tabla especial `registro_agentes.catalogo_ladas` al flujo de ladas consumido por UI (`/api/qr/ladas`) sin romper el catalogo operativo existente.

## Cambios aplicados
1. Backend (`backend/app/api/qr.py`):
   - Se agrego `LEGACY_LADAS_TABLE = "catalogo_ladas"`.
   - Se implemento `_sync_ladas_from_legacy_catalog(db)` para:
     - Leer `ID_PAIS/LADA/CIUDAD/ESTADO/PAIS` desde `registro_agentes.catalogo_ladas`.
     - Normalizar codigo LADA.
     - Deduplicar por codigo antes de upsert para evitar conflictos de indice unico.
     - Crear/reactivar/actualizar `ladas_catalogo` (catalogo operativo).
   - `GET /api/qr/ladas` ahora intenta sincronizar desde el catalogo especial antes de listar.
   - Se agrega campo de respuesta `source` para trazabilidad de origen en UI.

2. Frontend (`web/js/main.js`):
   - Se agrego nombre logico para `catalogo_ladas` en el catalogo de objetos de BD.

## Verificacion tecnica
Prueba ejecutada por script de backend:
- Resultado de sync: `source=100`, `normalized=57`, `created=57`, `updated=0`, `reactivated=0`.
- Conflicto detectado inicialmente por duplicados de codigo LADA en origen; resuelto con deduplicacion previa.

## Estado
- Integracion completada.
- El endpoint usado por los combos de UI queda alimentado por `registro_agentes.catalogo_ladas` (via sincronizacion a catalogo operativo).

## Limpieza de duplicados y control preventivo
- Se detectaron duplicados por `LADA` en `registro_agentes.catalogo_ladas`.
- Se aplico limpieza conservando 1 fila por `LADA` con criterio estable:
   - prioridad `ID_PAIS = 52`
   - luego `ID_PAIS`, `CIUDAD`, `ESTADO`, `PAIS` ascendente.
- Respaldo generado antes de limpiar:
   - `registro_agentes.catalogo_ladas_backup_20260322_160344`
- Resultado de limpieza:
   - antes: `100` filas
   - despues: `64` filas
   - grupos duplicados por `LADA`: `0`
- Se creo indice unico para prevenir reincidencia:
   - `ux_catalogo_ladas_lada` sobre `registro_agentes.catalogo_ladas(LADA)`.

## Verificacion final
- Duplicados en `registro_agentes.catalogo_ladas`: `0` grupos.
- Sincronizacion posterior correcta:
   - `source=64`, `normalized=57`, `created=0`, `updated=3`, `reactivated=0`.
