# CHECKPOINT OPERATIVO 2026-03-22 - Sincronizacion Altas/Cambios/Bajas con registro_agentes.agentes

## Objetivo
Corregir desfase donde agentes aparecian en UI operativa pero no en `registro_agentes.agentes`.

## Causa raiz
- El alta manual (`/api/qr/agentes/manual`) persistia en `datos_importados`.
- Cambios/Bajas (`/api/datos`) operaban sobre `datos_importados`.
- No existia sincronizacion hacia `registro_agentes.agentes`.

## Cambios aplicados
1. `backend/app/api/qr.py`
- Se agrego helper `_sync_legacy_agente_row(...)`.
- En `crear_agente_manual(...)` ahora se hace `UPSERT` en:
  - `registro_agentes.agentes` (`ID`, `Nombre`, `alias`, `Ubicacion`, `FP`, `FC`, `Grupo`).
- Si falla la sincronizacion, se corta la operacion con HTTP 500 para evitar datos "solo UI".

2. `backend/app/api/datos.py`
- Se agregaron helpers:
  - `_sync_legacy_agente_row(...)`
  - `_delete_legacy_agente_row(...)`
- `POST /api/datos` ahora sincroniza alta en `registro_agentes.agentes`.
- `PUT /api/datos/{dato_id}` ahora sincroniza cambios en `registro_agentes.agentes`.
- `DELETE /api/datos/{dato_id}` ahora aplica baja eliminando el registro en `registro_agentes.agentes`.
- `DELETE /api/datos/{dato_id}/hard-delete` intenta tambien eliminar el registro legado.

## Validacion tecnica
- Compilacion sintactica:
  - `c:/python314/python.exe -m py_compile backend/app/api/qr.py backend/app/api/datos.py`
- Resultado: OK (sin errores de compilacion).

## Resultado esperado
- Alta manual: aparece en UI y en `registro_agentes.agentes`.
- Edicion en Cambios y Bajas: se refleja en `registro_agentes.agentes`.
- Baja en Cambios y Bajas: desaparece de `registro_agentes.agentes`.
