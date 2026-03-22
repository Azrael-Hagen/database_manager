# CHECKPOINT OPERATIVO 2026-03-22 - Composicion de Base de Datos

## Resumen
Se aplico una composicion aditiva del esquema para fortalecer operacion, catalogos y control de sincronizacion sin romper compatibilidad.

## Cambios de codigo
1. `backend/app/database/orm.py`
- Se agregaron utilitarios internos para verificar columnas e indices.
- Se agrego ejecucion opcional segura para objetos no criticos cross-schema.
- Se incorporaron cambios de esquema:
  - Columna `datos_importados.estatus_codigo` (default `ACTIVO`).
  - Indices compuestos de rendimiento.
  - Tabla catalogo `cat_estatus_agente`.
  - Tabla `agente_eventos_operativos`.
  - Vista `vw_agentes_operacion_actual`.
  - Vista `vw_control_sync_agentes`.

2. `backend/app/models.py`
- Se agrego columna ORM `estatus_codigo` al modelo `DatoImportado`.

3. `backend/app/api/qr.py`
- Alta manual establece `estatus_codigo = ACTIVO`.

4. `backend/app/api/datos.py`
- Baja logica establece `estatus_codigo = BAJA`.

## Ejecucion de migracion
- Comando aplicado:
  - `python -c "from app.database.orm import init_db; init_db()"`
- Resultado: `SCHEMA_OK`.

## Validacion posterior
- Objetos nuevos confirmados en BD:
  - Tablas: `cat_estatus_agente`, `agente_eventos_operativos`.
  - Vistas: `vw_agentes_operacion_actual`, `vw_control_sync_agentes`.
  - Columna: `datos_importados.estatus_codigo`.
- Estado inicial de sincronizacion detectado:
  - `EN_SYNC = 1`.

## Notas
- Los cambios son backward-compatible y no eliminan estructuras existentes.
- `registro_agentes` se mantiene como esquema auxiliar/legado para compatibilidad.
