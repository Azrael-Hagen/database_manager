# Guia de Automatizacion - Reporte de Conciliacion Operativa

## Scripts disponibles
- Python: `backend/scripts/generar_reporte_conciliacion.py`
- PowerShell (wrapper Windows): `scripts/generar-reporte-conciliacion.ps1`
- SQL base de referencia: `scripts/reporte_conciliacion_operativa_semanal.sql`

## Salidas
Los archivos se generan en:
- `logs/reportes_conciliacion/`

Formatos:
- `conciliacion_detalle_YYYYMMDD_HHMMSS.csv`
- `conciliacion_resumen_YYYYMMDD_HHMMSS.csv`
- `conciliacion_YYYYMMDD_HHMMSS.json`

## Ejecucion manual
Desde raiz del proyecto:

```powershell
$env:PYTHONPATH='backend'
python backend/scripts/generar_reporte_conciliacion.py --weeks 12 --output-format both
```

Filtrando por agente:

```powershell
$env:PYTHONPATH='backend'
python backend/scripts/generar_reporte_conciliacion.py --from-date 2026-03-01 --to-date 2026-03-25 --agent-id 123
```

Usando wrapper PowerShell:

```powershell
./scripts/generar-reporte-conciliacion.ps1 -Weeks 12 -OutputFormat both
```

## Programacion semanal en Windows Task Scheduler
Ejemplo para correr cada lunes 07:00:

```powershell
schtasks /Create /TN "DM_Reporte_Conciliacion_Semanal" /SC WEEKLY /D MON /ST 07:00 /TR "powershell -NoProfile -ExecutionPolicy Bypass -File \"C:\Users\Azrael\OneDrive\Documentos\Herramientas\database_manager\scripts\generar-reporte-conciliacion.ps1\" -Weeks 12 -OutputFormat both" /F
```

## Validacion recomendada post-ejecucion
1. Verificar que existan los 2 CSV y el JSON del timestamp actual.
2. Revisar en el CSV detalle filas con `estatus_conciliacion = REVISAR_MOVIMIENTOS`.
3. Revisar en el CSV resumen columnas `agentes_con_diferencia` y `delta_total_pagos_vs_mov`.
