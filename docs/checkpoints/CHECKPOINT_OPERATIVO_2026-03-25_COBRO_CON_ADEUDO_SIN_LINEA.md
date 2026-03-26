# CHECKPOINT OPERATIVO 2026-03-25 - Cobro con Adeudo Sin Linea

## Objetivo
Permitir registrar cobros cuando el agente tiene adeudo, aunque no tenga linea activa asignada.

## Cambio funcional
- Se removio el bloqueo en endpoint de pago semanal que devolvia error 400 cuando no existia linea activa.
- Flujo de recibo y resumen se mantiene, usando linea nula cuando no hay asignacion.

## Archivos modificados
- `backend/app/api/qr.py`
- `tests/test_sin_linea_e2e.py`

## Pruebas
- Nuevo caso E2E: cobro con adeudo sin linea activa.
- Suite E2E completa ejecutada en verde.

## Resultado
La operacion de cobro ya no depende de tener linea activa y respeta el criterio operativo solicitado.
