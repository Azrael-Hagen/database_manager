# CHECKPOINT TECNICO PREVIO - 2026-03-23 - AJUSTE MANUAL DE DEUDA UI

## Objetivo del bloque
Agregar control claro en UI para editar manualmente cuánto debe un agente, con impacto real en el cálculo de deuda.

## Alcance planeado
- Backend: exponer endpoint para leer/aplicar ajuste manual por agente.
- Backend: integrar ajuste manual en resumen de cobranza.
- Frontend: agregar sección visible en QR y Cobros para consultar/aplicar/limpiar ajuste.
- Validación: ejecutar pruebas focalizadas y suite de regresión.

## Riesgos identificados
- No romper lógica existente de pago semanal y liquidación total.
- Mantener consistencia entre saldo mostrado en UI y cálculo backend.

## Criterio de salida
- Ajuste manual visible y usable en UI.
- Resumen de pagos refleja ajuste aplicado.
- Pruebas en verde.
