# CHECKPOINT TECNICO — 2026-03-28 — Smart Import Conciliacion IA (PRE)

## Objetivo
- Extender importador inteligente para conciliacion contra BD existente.
- Detectar actualizaciones en agentes y lineas (numero_voip, ubicacion, alias, etc.).
- Detectar datos de prueba e incoherencias.
- Solicitar confirmacion explicita antes de aplicar cambios.

## Alcance
- backend/app/importers/smart_importer.py
- backend/app/api/smart_import.py
- web/js/smartImport.js
- tests/test_smart_import.py

## Criterios de aceptacion
- Preview muestra cambios propuestos por agente (campos y linea).
- Preview incluye diagnostico IA (test data, incoherencias, sugerencias).
- Execute aplica cambios de agente y linea cuando corresponda.
- UI pide confirmacion antes de ejecutar.
- E2E de smart-import en verde.

## Riesgos
- Match agresivo de agente incorrecto.
- Reasignaciones de linea no deseadas.

## Mitigacion
- Matching por prioridad conservadora (email/telefono/alias+nombre/numero_voip) con trazabilidad.
- Preview detallado + confirmacion obligatoria en UI antes de execute.
