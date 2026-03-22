# Checkpoint Operativo UI + Pagos + QR Seguro (2026-03-22)

## Objetivo del bloque
- Ajustar la UI de Altas para eliminar el campo Telefono en alta manual.
- Alinear el flujo operativo a campos realmente usados por backend/BD en gestion de agentes.
- Implementar vista operativa de agentes con extension y estado de pago semanal.
- Persistir comprobantes de pago por un tiempo definido para reimpresion.
- Endurecer QR para que quede ligado a agente + linea activa y no sea transferible.

## Hallazgos previos
- En `datos_importados` existe columna `telefono`, pero la operacion de Altas ya depende del inventario sincronizado de lineas PBX.
- El comprobante actual se mantiene solo en memoria frontend (`lastReceiptData`) y se pierde al recargar.
- El QR actual se basa en UUID de agente (`/public/verify/{uuid}`), por lo que no obliga atadura criptografica a linea asignada.

## Criterio de aceptacion
1. Altas de agentes ya no muestra ni envía campo Telefono.
2. Existe una vista SQL para estado agente + extension + pago semanal.
3. Cada registro de pago genera un recibo persistente con expiracion por retencion configurable.
4. Se puede reimprimir recibo desde backend mientras no expire.
5. QR generado para agente queda firmado y validado contra agente + linea activa (token seguro); QR anterior deja de ser valido tras rotacion/cambio.
6. Verificacion del sistema y pruebas de humo del bloque completadas.

## Implementacion ejecutada
- UI Altas: eliminado input de telefono en alta manual y eliminado envio de `telefono` en payload de `crearAgenteManual`.
- Backend QR:
	- QR seguro firmado HMAC con `SECRET_KEY`, ligado a `agente_id + linea_id + expiracion`.
	- Nuevo endpoint publico seguro: `GET /api/qr/public/verify-secure/{token}`.
	- Generacion de QR individual ahora requiere linea activa asignada y emite URL segura (no UUID plano).
	- Soporte de lectura por scanner para URL segura (`/verify-secure/...`).
- Recibos persistentes:
	- Nueva tabla `recibos_pago` con expiracion e historial de impresiones.
	- Registro de pago semanal ahora crea/actualiza recibo persistente y devuelve token de recibo.
	- Endpoints: `GET /api/qr/recibos` y `GET /api/qr/recibos/{token_recibo}`.
- Vista operativa:
	- Nueva vista SQL `vw_agentes_extensiones_pago_actual` (agente + extension activa + estado de pago semanal).
	- Nuevo endpoint API: `GET /api/qr/agentes/estado-pago`.
	- UI QR incorpora tabla de vista operativa y listado de recibos guardados con accion reimprimir.

## Validacion de cierre
- `backend/verify_system.py`: `8/8` pruebas pasadas.
- `HAS_RECIBOS_TABLE = 1` y `HAS_ESTADO_VIEW = 1` en `database_manager`.
- Consultas runtime:
	- `SELECT COUNT(*) FROM vw_agentes_extensiones_pago_actual` ejecuta correctamente (`VIEW_ROWS=2`).
	- `SELECT COUNT(*) FROM recibos_pago` ejecuta correctamente (`RECIBOS_ROWS=0`, sin datos de pago en el momento de validacion).
- Nota de humo funcional:
	- No fue posible validar flujo completo de token seguro/recibo con datos reales porque no habia agente con asignacion activa ni pagos existentes en ese instante (`NO_ACTIVE_ASSIGNMENT`, `NO_PAGOS`).

## Validacion E2E real posterior
- Se ejecuto prueba end-to-end con datos temporales marcados (`E2E_TMP_<id>`), simulando usuario admin/capture autenticado para rutas protegidas:
	1) `POST /api/qr/lineas/sync` -> `200`.
	2) `GET /api/qr/lineas` -> seleccion de linea libre real (`linea_id=5`, numero `1000`).
	3) `POST /api/qr/agentes/manual` (modo manual con linea existente) -> `200`, `agente_id=26`.
	4) `GET /api/qr/agente/26/qr` -> `200` (QR seguro generado).
	5) `GET /api/qr/public/verify-secure/{token}` -> `200`.
	6) `POST /api/qr/pagos` -> `200` (recibo persistente generado).
	7) `GET /api/qr/recibos?agente_id=26` -> `200`, `RECIBOS_COUNT=1`.
	8) `GET /api/qr/recibos/{token}` -> `200` (recuperacion/reimpresion).
	9) `GET /api/qr/agentes/estado-pago?semana=2026-03-16&search=E2E_TMP...` -> `200`, `ESTADO_ROWS=1`, `estado_pago=PAGADO`.

## Depuracion de informacion de test
- Limpieza puntual post-E2E (por marcador `E2E_TMP_...`) completada:
	- `datos_importados`, `pagos_semanales`, `recibos_pago`, `agente_linea_asignaciones`.
	- Conteo remanente del marcador: `agents=0`, `pagos=0`, `recibos=0`.
- Barrido adicional global de residuos con patrones `E2E`/`TEMP` en tablas operativas:
	- Antes: `{datos_importados:0, pagos_semanales:0, recibos_pago:0, lineas_telefonicas:0}`.
	- Despues: `{datos_importados:0, pagos_semanales:0, recibos_pago:0, lineas_telefonicas:0}`.
