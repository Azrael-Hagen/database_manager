# CHECKPOINT TECNICO - 2026-04-03 - FIX LIBERAR LINEAS UNDEFINED (CIERRE)

Estado: CERRADO
Referencia PRE: CHECKPOINT_TECNICO_2026-04-03_FIX_LIBERAR_LINEAS_UNDEFINED_PRE.md

## Problema reportado
En Cambios y Bajas se estaba enviando:
- POST /api/qr/lineas/undefined/liberar

Esto provocaba 422 por `linea_id` invalido en path parameter.

## Causa raiz
Desalineacion de shape en `agent.lineas`:
- Backend entregaba `linea_id` (sin `id`) en lineas activas de agente.
- Frontend en `liberarLineasAgente` consumia `line.id`.

Resultado: `line.id === undefined` y URL invalida.

## Correcciones aplicadas

### Frontend
Archivo: web/js/main.js
- `liberarLineasAgente` ahora normaliza ID de linea usando `id | linea_id | linea.id`.
- Se agrega validacion defensiva para abortar con mensaje claro si una linea no trae ID valido.
- `liberarLinea` valida `lineaId` numerico positivo antes de llamar API.

Archivo: web/js/api-client.js
- Se agrega helper `_requirePositiveInt`.
- Se aplica validacion en `actualizarLinea`, `asignarLinea`, `liberarLinea`, `desactivarLinea`.
- Se evita construir endpoints con segmentos `undefined/null/no numericos`.

### Backend
Archivo: backend/app/api/qr.py
- `_agent_active_lines` y `_agent_active_lines_from_prefetch` ahora incluyen ambos campos:
  - `id`
  - `linea_id`
- `liberar_linea` valida `agente_id` del payload y retorna 400 si es invalido.

## Pruebas agregadas/actualizadas
Archivo: tests/test_sin_linea_e2e.py
- Nuevo test: `test_qr_agentes_lineas_incluye_id_y_linea_id`.
- Nuevo test: `test_liberar_linea_rechaza_agente_id_invalido`.

## Validacion ejecutada
1. Flujo focalizado lineas/agentes
- Comando: `PYTHONPATH=backend pytest tests/test_sin_linea_e2e.py -k "lineas or agentes" -q`
- Resultado: 9 passed

2. E2E completo sin_linea
- Comando: `PYTHONPATH=backend pytest tests/test_sin_linea_e2e.py -q`
- Resultado: 52 passed

3. Movil/offline (regresion)
- Comando: `PYTHONPATH=backend pytest tests/test_offline_sync.py tests/test_api.py -k "mobile_route or mobile_shell" -q`
- Resultado: 5 passed (subset movil), sin regresiones

## Versionado
- `backend/app/versioning.py` -> 1.5.0-rev7
- `deploy/version-info.json` -> current revision 7 + history entry
- `deploy/CHANGELOG.server.md` -> entrada 1.5.0-rev7

## Resultado final
Flujo de liberar lineas corregido y blindado contra IDs invalidos, con compatibilidad de shape backend/frontend y regresiones E2E en verde.
