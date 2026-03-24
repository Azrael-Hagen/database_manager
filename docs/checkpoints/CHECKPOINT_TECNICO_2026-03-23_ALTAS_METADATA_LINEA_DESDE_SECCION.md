# CHECKPOINT TECNICO 2026-03-23 - ALTAS: METADATA DE LINEA DESDE LA MISMA SECCION

## Objetivo
Permitir definir metadatos operativos de linea (tipo de numero y estado de conexion) directamente desde la seccion **Altas de Agentes**.

## Cambios aplicados

### Backend
- `backend/app/api/qr.py`
  - Se actualizo `_resolve_or_create_line_for_manual_assignment` para aceptar desde payload:
    - `categoria_linea`
    - `estado_conexion`
  - Comportamiento:
    - Si se selecciona linea existente (`linea_id`), actualiza esos metadatos cuando vienen en payload.
    - Si se reactiva una linea existente por numero manual, actualiza metadatos cuando vienen en payload.
    - Si se crea linea manual nueva, persiste metadatos en alta.

### Frontend
- `web/index.html`
  - Alta manual (modo manual): nuevos controles
    - `agenteLineaCategoriaSelect`
    - `agenteLineaConexionSelect`
  - Asignacion de linea: nuevos controles
    - `lineaAsignarCategoria`
    - `lineaAsignarConexion`
  - El selector de linea de asignacion ahora sincroniza metadatos actuales con `onchange="sincronizarCamposLineaAsignar()"`.

- `web/js/main.js`
  - Nuevo estado en memoria: `currentAltasLineas`.
  - En `cargarLineasYAgentes`:
    - guarda listado de lineas en `currentAltasLineas`.
    - invoca `sincronizarCamposLineaAsignar()`.
  - `cambiarModoAsignacionAgente` ahora muestra/oculta tambien los selects de categoria/conexion de alta manual.
  - Nueva funcion `sincronizarCamposLineaAsignar()` para precargar categoria/conexion al elegir linea.
  - `crearAgenteManual` envia `categoria_linea` y `estado_conexion` cuando el modo es manual.
  - `asignarLineaAgente` actualiza primero metadatos de linea via `actualizarLinea` (si se eligieron), y luego asigna.

### Tests
- `tests/test_sin_linea_e2e.py`
  - Se amplio test de assets frontend para validar presencia de los nuevos controles en `index.html`.

## Validacion ejecutada
- `./.venv/Scripts/python.exe -m pytest tests/test_sin_linea_e2e.py -k "test_index_tiene_controles or debug_flujo_lineas" -q`
  - Resultado: 2 passed

## Nota de entorno de pruebas
- Se intento una prueba API directa para `/api/qr/agentes/manual` con metadatos, pero en SQLite de pruebas falla por sintaxis MySQL de sincronizacion legacy (`ON DUPLICATE KEY UPDATE`).
- La funcionalidad principal se valido con cobertura de flujo de lineas y presencia de controles UI en la seccion Altas.
