# CHECKPOINT OPERATIVO 2026-03-25 - Reporte SQL de Conciliacion Semanal

## Objetivo
Dejar un reporte SQL de auditoria operativa semanal para conciliar:
- `pagos_semanales`
- `cobros_movimientos`
- `saldo calculado` acumulado

Cumpliendo base por defecto del proyecto: `database_manager`.

## Entregable
- Script agregado: `scripts/reporte_conciliacion_operativa_semanal.sql`

## Alcance del reporte
- Filtros por rango de semanas (`@fecha_desde`, `@fecha_hasta`) y opcional por `@agente_id`.
- Cruce por agente/semana entre:
  - monto pagado en `pagos_semanales`
  - neto de movimientos de pago en `cobros_movimientos`
  - diferencia contable `pagos - movimientos`
- Calculo de deuda teorica semanal:
  - lineas activas facturables
  - cuota semanal de `config_sistema` (`CUOTA_SEMANAL`, default 300.00)
  - `cargo_inicial` en semana de arranque
- Calculo acumulado:
  - deuda acumulada calculada
  - total abonado acumulado
  - saldo calculado acumulado
- Etiqueta de conciliacion:
  - `OK`
  - `CON_SALDO`
  - `REVISAR_MOVIMIENTOS`
- Resumen ejecutivo semanal consolidado.

## Criterios de limpieza detectados (sin ejecutar borrados)
1. Revisar archivos de diagnostico temporales en `tmp/` y eliminar los que ya no se usen en operacion.
2. Revisar `backend/verification_results.json` para moverlo a historico o regenerarlo bajo demanda (evitar archivo stale en raiz backend).
3. Consolidar guias/checkpoints historicos duplicados en un indice maestro para reducir ruido documental.
4. Confirmar si vistas espejo en `registro_agentes` siguen requeridas en todos los entornos; si no, marcarlas para retiro controlado.

## Verificacion operativa esperada
1. Ejecutar pruebas backend clave de persistencia/consultas.
2. Validar endpoint de salud.
3. Ejecutar script SQL en base activa para verificar salida coherente.

## Riesgos y notas
- El saldo calculado del reporte es de auditoria operativa (contable semanal/acumulada) y puede diferir de escenarios historicos complejos si hubo ajustes externos no registrados.
- No se realizaron eliminaciones fisicas de tablas/vistas/archivos en este bloque para evitar impacto sobre funcionalidades validadas sin autorizacion explicita.