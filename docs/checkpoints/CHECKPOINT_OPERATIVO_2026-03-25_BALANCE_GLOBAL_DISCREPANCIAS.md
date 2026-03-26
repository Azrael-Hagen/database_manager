# CHECKPOINT OPERATIVO 2026-03-25 - Balance Global y Discrepancias de Cobranza

## Objetivo
Agregar balance financiero global semanal persistido en BD y exponer discrepancias de conciliacion para control operativo.

## Cambios aplicados
- `backend/app/utils/pagos.py`
  - `obtener_reporte_semanal` ahora incluye totales financieros globales:
    - `deuda_total_global`
    - `total_abonado_global`
    - `saldo_global`
    - `monto_semana_reportado`
    - `monto_semana_ledger`
    - `discrepancia_semana`
    - `discrepancia_saldo`
  - Agrega bloque `discrepancias` con codigos de control.
- `backend/app/models.py`
  - Nuevo modelo `CobranzaSemanalSnapshot` para auditoria de balance semanal.
- `backend/app/api/qr.py`
  - `GET /api/qr/reporte-semanal` persiste snapshot semanal y devuelve bloque `snapshot`.
- `backend/app/database/orm.py`
  - Asegura tabla `cobranza_semanal_snapshots` en MySQL startup.
- `web/js/main.js`
  - Resumen semanal muestra deuda/abono/saldo global, diferencias y discrepancias.
  - Muestra metadata de snapshot persistido en BD.
  - Edicion manual de pago mejora contexto mostrando monto actual en prompt.

## Pruebas
- `tests/test_sin_linea_e2e.py`
  - Nuevo bloque `TestReporteSemanalGlobal` con validaciones de:
    - totales financieros globales
    - deteccion de discrepancias por pagos duplicados
    - persistencia de snapshot en BD

## Validacion ejecutada
- `c:/python314/python.exe -m pytest ../tests/test_sin_linea_e2e.py -k "ReporteSemanalGlobal or TotalesCobranzaQr"` -> 3 passed
- `c:/python314/python.exe -m pytest ../tests/test_sin_linea_e2e.py` -> 46 passed

## Resultado
La vista semanal ya entrega balance global auditable, guarda snapshots en BD para trazabilidad y expone discrepancias operativas para accion correctiva.
