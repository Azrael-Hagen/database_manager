# CHECKPOINT OPERATIVO 2026-03-22 - Verificacion DB y visibilidad en registro_agentes

## Solicitud
Confirmar que los cambios de composicion de BD existen y, si no eran visibles, aplicar ajustes para verlos desde la BD por defecto `registro_agentes`.

## Hallazgo
- Los cambios SI existian en `database_manager`:
  - Tablas: `cat_estatus_agente`, `agente_eventos_operativos`.
  - Vistas: `vw_agentes_operacion_actual`, `vw_control_sync_agentes`.
- En `registro_agentes` no aparecian porque esos objetos estaban en la BD canonica (`database_manager`).

## Accion aplicada
Se agregaron vistas espejo en `registro_agentes`:
- `vw_dm_agentes_operacion_actual`
- `vw_dm_control_sync_agentes`
- `vw_dm_cat_estatus_agente`

Implementado en `backend/app/database/orm.py` y aplicado con `init_db()`.

## Validacion final
- Inventario en `registro_agentes`:
  - Vistas: `datos_importados`, `vw_dm_agentes_operacion_actual`, `vw_dm_cat_estatus_agente`, `vw_dm_control_sync_agentes`.
- Querys de prueba:
  - `SELECT COUNT(*) FROM registro_agentes.vw_dm_agentes_operacion_actual;` -> OK.
  - `SELECT estado_sync, COUNT(*) FROM registro_agentes.vw_dm_control_sync_agentes GROUP BY estado_sync;` -> `EN_SYNC`.
  - `SELECT codigo, nombre FROM registro_agentes.vw_dm_cat_estatus_agente ORDER BY orden;` -> `ACTIVO`, `SUSPENDIDO`, `BAJA`.

## Nota operativa
Algunas interfaces muestran solo tablas base en el selector principal. Para ver estos cambios, consultar la seccion de vistas o ejecutar SQL directo en `registro_agentes`.
