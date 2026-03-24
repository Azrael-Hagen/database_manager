# CHECKPOINT TECNICO - 2026-03-23 - GESTION LINEAS + QR UI + E2E REV5

## Objetivo
Atender bloque solicitado por usuario: seccion exclusiva de lineas, correccion de botones QR sin accion visible y validacion E2E/debug.

## Cambios aplicados
- Backend QR/Lineas:
  - Listado de lineas ahora incluye inventario activo completo (PBX + manual).
  - Alta/reactivacion de lineas manuales habilitada en `POST /api/qr/lineas`.
  - Edicion de linea habilitada en `PUT /api/qr/lineas/{linea_id}`.
  - Fallback seguro en sincronizacion PBX cuando no existe tabla legacy.
- Frontend:
  - Seccion nueva `Gestion de Lineas` con formulario de alta/edicion y tabla exclusiva.
  - Acciones por linea: editar, liberar, desactivar y abrir QR del agente cuando aplica.
  - Botones QR de secciones operativas ajustados para abrir modal visible y coherente.
- Pruebas:
  - Se agrega test debug E2E para flujo crear/editar/asignar/liberar/listar lineas.

## Verificacion
- Debug test:
  - `c:/python314/python.exe -m pytest -q tests/test_sin_linea_e2e.py -k lineas -vv -s`
  - Resultado: `1 passed`
- Suite completa:
  - `c:/python314/python.exe -m pytest -q`
  - Resultado: `45 passed`

## Resultado
UI coherente con flujo operativo solicitado, gestion de lineas visible y funcional, botones QR operativos y validacion end-to-end completada.