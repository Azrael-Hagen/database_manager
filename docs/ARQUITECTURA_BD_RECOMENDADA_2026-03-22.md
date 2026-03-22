# Arquitectura BD recomendada (2026-03-22)

## 1) Base canonica operativa
La base operativa canonica del sistema es `database_manager`.

Tablas principales de operacion:
- `datos_importados`: maestro de agentes.
- `lineas_telefonicas`: inventario operativo de lineas.
- `agente_linea_asignaciones`: historico de asignacion/liberacion.
- `pagos_semanales`: estado de pago semanal.
- `recibos_pago`: comprobantes persistentes.
- `ladas_catalogo`: catalogo operativo de ladas.
- `usuarios` y `auditoria_acciones`: seguridad y trazabilidad.

## 2) Base legado / fuente auxiliar
`registro_agentes` se usa como fuente auxiliar y compatibilidad:
- `extensions_pbx`: fuente de inventario PBX.
- `agentes`: tabla heredada para integraciones/consulta externa.

## 3) Mejoras aplicadas en este bloque
- Catalogo de estatus: `cat_estatus_agente`.
- Columna de estatus en agente: `datos_importados.estatus_codigo`.
- Bitacora dedicada de eventos operativos: `agente_eventos_operativos`.
- Vista consolidada operativa: `vw_agentes_operacion_actual`.
- Vista de control de sincronizacion legado: `vw_control_sync_agentes`.
- Indices compuestos para consultas frecuentes.

## 4) Vistas recomendadas para operacion
- `vw_agentes_operacion_actual` para pantallas de operacion (altas, cambios, pagos, asignacion).
- `vw_agentes_extensiones_pago_actual` para estado semanal rapido.
- `vw_control_sync_agentes` para monitorear desalineaciones entre canonico y legado.

## 5) Convenciones de modelado recomendadas
- Mantener llaves numericas internas (`id`) como PK.
- Conservar `uuid` para enlaces/QR/public endpoints.
- Usar estado logico (`es_activo` + `estatus_codigo`) en lugar de borrado fisico.
- No usar campo Empresa para flujo operativo de agentes.
- Registrar cambios relevantes en `agente_eventos_operativos` y `auditoria_acciones`.

## 6) Siguiente fase recomendada
Fase A (sin riesgo):
- Empezar a escribir eventos en `agente_eventos_operativos` desde endpoints de alta, edicion, asignacion, liberacion, baja, pago.

Fase B (normalizacion):
- Consolidar los campos hoy en JSON (`datos_adicionales`) a columnas dedicadas para reporting avanzado:
  - alias, ubicacion, fp, fc, grupo, numero_voip.

Fase C (hardening):
- Definir reglas de reconciliacion automatica con `registro_agentes.agentes` y alertas cuando `vw_control_sync_agentes` detecte `DESALINEADO` o `FALTANTE_EN_LEGACY`.

## 7) Query de salud operativa sugerida
Monitoreo rapido de sincronizacion:

```sql
SELECT estado_sync, COUNT(*) AS total
FROM vw_control_sync_agentes
GROUP BY estado_sync
ORDER BY estado_sync;
```
