# CHECKPOINT TECNICO 2026-03-24 - LINEAS METADATA + QR

## Objetivo
Implementar soporte operativo para metadatos de linea en flujo completo (BD + API + UI):
- categoria de linea (FIJO/MOVIL/NO_DEFINIDA)
- estado de conexion (CONECTADA/DESCONECTADA/DESCONOCIDA)
- fecha de ultimo uso

## Cambios aplicados

### Backend
- `backend/app/models.py`
  - Se agregaron columnas en `LineaTelefonica`:
    - `categoria_linea`
    - `estado_conexion`
    - `fecha_ultimo_uso`
- `backend/app/database/orm.py`
  - Migracion guardada en runtime para crear columnas faltantes en `lineas_telefonicas`.
  - Se agregaron indices:
    - `ix_lineas_telefonicas_categoria_linea`
    - `ix_lineas_telefonicas_estado_conexion`
- `backend/app/api/qr.py`
  - Se agrego validacion/normalizacion para `categoria_linea` y `estado_conexion`.
  - Se agrego parseo de `fecha_ultimo_uso` (ISO date/datetime).
  - `GET /api/qr/lineas` ahora retorna los 3 campos nuevos.
  - `POST /api/qr/lineas` acepta y persiste los 3 campos nuevos.
  - `PUT /api/qr/lineas/{linea_id}` acepta y persiste los 3 campos nuevos.
  - Sincronizacion PBX inicializa defaults cuando faltan valores.

### Frontend
- `web/index.html`
  - Formulario de Gestion de Lineas:
    - selector de categoria
    - selector de estado de conexion
    - input datetime-local de ultimo uso
- `web/js/main.js`
  - Formulario de edicion/alta con carga y limpieza de nuevos campos.
  - Payload de guardado envia `categoria_linea`, `estado_conexion`, `fecha_ultimo_uso`.
  - Tabla de Gestion de Lineas muestra categoria, conexion y ultimo uso.
  - Tabla de Estado de Lineas muestra categoria, conexion y ultimo uso.

### Tests
- `tests/test_sin_linea_e2e.py`
  - Se amplio `test_debug_flujo_lineas_crear_editar_asignar_y_listar` para validar:
    - create con metadatos
    - update con metadatos
    - listado ocupado con metadatos persistidos

## Validacion ejecutada
- `./.venv/Scripts/python.exe -m pytest tests/test_sin_linea_e2e.py -k "test_debug_flujo_lineas_crear_editar_asignar_y_listar" -q`
  - Resultado: 1 passed
- `./.venv/Scripts/python.exe -m pytest tests/test_sin_linea_e2e.py -k "qr and not debug_flujo" -q`
  - Resultado: 10 passed
- `./.venv/Scripts/python.exe -m pytest tests/test_sin_linea_e2e.py -k "linea or qr or debt or alta" -q`
  - Resultado: 29 passed

## Notas
- Se verifico que los botones/acciones QR mantienen flujo operativo en pruebas QR del backend.
- No se introdujo el campo Empresa en formularios/tablas de gestion.
- Los nuevos datos mostrados en UI provienen de API persistida en BD.
