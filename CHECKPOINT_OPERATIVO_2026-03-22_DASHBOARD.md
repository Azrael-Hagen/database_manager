# Checkpoint Operativo Dashboard (2026-03-22)

## Estado previo del bloque
- El dashboard ya consume `/api/dashboard/summary` y muestra usuarios en linea, importaciones recientes y metadatos de BD.
- La UI sigue cumpliendo la regla de no mostrar datos fuera de BD y mantiene `registro_agentes` como base predeterminada en la seccion Datos.
- La validacion directa del resumen devolvio estructura correcta pero con `registros` y `qr_generados` en `0`.

## Hallazgo tecnico confirmado
- Los registros existen realmente en `database_manager.datos_importados` y en la vista `registro_agentes.datos_importados`.
- El conteo filtrado por `COALESCE(es_activo, 1) = 1` devuelve `0` porque los registros actuales tienen `es_activo = 0`.
- Esto significa que el dashboard necesita distinguir entre totales reales, activos e inactivos para no aparentar ausencia de datos cuando en realidad hay historico persistido.

## Objetivo del siguiente bloque
- Corregir el backend del dashboard para separar totales, activos, inactivos y QR reales.
- Agregar senales operativas utiles: alertas, lineas, agentes recientes y actividad de 7 dias.
- Actualizar la UI para mostrar estas metricas sin inventar informacion.