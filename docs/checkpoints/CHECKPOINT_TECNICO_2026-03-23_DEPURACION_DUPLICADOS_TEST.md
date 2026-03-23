# CHECKPOINT TECNICO - 2026-03-23 (Depuracion de Duplicados y Test Data)

## Objetivo
Eliminar datos de prueba y registros duplicados operativos en `database_manager.datos_importados`, manteniendo integridad referencial y sincronia con legado.

## Diagnostico previo
- Activos en `datos_importados`: 204
- Test-like activos detectados: 1 (ID 39, nombre `Fix2 QR 1774227040`)
- Duplicados exactos seguros (sin refs): 7 IDs
- Tabla temporal detectada: `temp_usuarios_historial` (USADA por backend, NO eliminar)

## Criterio de depuracion
1. Borrar test-like activos por patron (`test|e2e|fix|demo|tmp|temporal|prueba`).
2. Borrar solo duplicados exactos por firma operativa:
   - nombre, telefono, alias, ubicacion, fp, fc, grupo, numero_voip
   - conservar el menor ID por grupo
3. Excluir de borrado cualquier agente con referencias en:
   - `agente_linea_asignaciones`
   - `pagos_semanales`
   - `recibos_pago`
4. Replicar limpieza en `registro_agentes.agentes` por ID para mantener espejo limpio.

## Rollback operativo
En caso de incidente, restaurar ultimo backup SQL disponible en `tmp/chosen_backups/`.
