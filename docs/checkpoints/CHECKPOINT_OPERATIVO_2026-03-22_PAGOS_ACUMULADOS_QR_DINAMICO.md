# CHECKPOINT OPERATIVO 2026-03-22 - Pagos Acumulados + QR Dinamico

## Objetivo
- Fijar cuota semanal en 300 MXN.
- Soportar deuda acumulada por semanas, abonos y liquidacion total.
- Permitir edicion manual de pagos por administrador.
- Garantizar QR por agente: fallback por UUID sin linea y QR seguro cuando existe linea activa.

## Cambios backend
1. `backend/app/utils/pagos.py`
- Se agrego `resumen_cobranza_agente(...)` para calcular:
  - deuda_total
  - total_abonado
  - saldo_acumulado
  - semanas_pendientes
  - estado semanal
- El reporte semanal incorpora campos acumulados y `pago_id`.

2. `backend/app/api/qr.py`
- `POST /api/qr/pagos` ahora:
  - acepta `liquidar_total`
  - registra abonos acumulativos por semana
  - calcula pagado semanal por cuota
  - retorna saldo/deuda acumulada
- `PUT /api/qr/pagos/{pago_id}` para edicion manual admin.
- `GET /api/qr/pagos/resumen/{agente_id}` para resumen acumulado.
- QR dinamico con helper `_refresh_agent_qr_for_state(...)`:
  - si hay linea activa -> QR seguro firmado
  - si no hay linea -> QR fallback por UUID
- Se refresca QR automaticamente en:
  - alta manual
  - asignacion de linea
  - liberacion de linea

3. `backend/app/schemas.py`
- `PagoSemanalCrear.telefono` ahora opcional.
- Nuevo esquema `PagoSemanalAdminActualizar`.

## Cambios frontend
1. `web/index.html`
- Form de pagos: checkbox `Liquidar adeudo acumulado`.
- Campo `Observaciones`.
- Panel `resumenPagoAgenteContainer`.

2. `web/js/api-client.js`
- `getResumenPagoAgente(...)`
- `editarPagoSemanalAdmin(...)`

3. `web/js/main.js`
- Registro de pago envia `liquidar_total` y observaciones.
- Se muestra saldo acumulado y abonado acumulado en verificacion/comprobante.
- Se agrega `consultarResumenPagoActual()`.
- En reporte semanal admin puede editar monto con boton `Editar Pago`.

## Configuracion aplicada
- Cuota semanal fijada en `300.00` via `config_sistema`.

## Verificaciones
- Sin errores de analisis en archivos modificados.
- Compilacion Python de backend modificada sin errores.
- Cuota final confirmada: `300.0`.

## Observacion de datos
- Actualmente no hay agentes activos en `database_manager.datos_importados`, por lo que el refresco masivo de QR no genero archivos en esta corrida (`total=0`).
- En cuanto existan agentes activos, el QR por agente se genera/actualiza automaticamente.
