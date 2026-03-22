# Checkpoint Operativo Sync extensions_pbx (2026-03-22)

## Objetivo del bloque
- Corregir el inventario de lineas para que el flujo de Altas de Agentes y asignaciones opere sobre datos sincronizados desde `registro_agentes.extensions_pbx`.

## Hallazgo tecnico confirmado
- El backend de QR/altas trabaja sobre `database_manager.lineas_telefonicas`.
- La tabla fuente `registro_agentes.extensions_pbx` contiene 227 registros y no existe en `database_manager`.
- No existe sincronizacion automatica entre `registro_agentes.extensions_pbx` y `database_manager.lineas_telefonicas`.
- El flujo actual puede crear lineas locales aisladas que no representan la fuente real importada.

## Criterio de aceptacion del bloque
1. Las lineas listadas para altas y asignacion se sincronizan desde `registro_agentes.extensions_pbx`.
2. Las lineas sincronizadas quedan reflejadas en `database_manager.lineas_telefonicas`.
3. Las altas manuales y asignaciones ya no dependen de lineas locales de prueba fuera de la fuente sincronizada.
4. Se valida con consultas reales a BD y se limpian rastros temporales/test.

## Cierre del bloque
- Se agrego configuracion explicita para la fuente `PBX_DB_NAME` y `PBX_EXTENSIONS_TABLE`.
- El backend sincroniza inventario desde `registro_agentes.extensions_pbx` hacia `database_manager.lineas_telefonicas` antes de listar, asignar o resolver lineas para altas.
- El flujo operativo de lineas en altas/asignaciones queda restringido a lineas sincronizadas, evitando crear lineas locales sueltas fuera de la fuente importada.
- Validacion real posterior al cambio:
	- `registro_agentes.extensions_pbx`: 227 registros.
	- `database_manager.lineas_telefonicas` activas sincronizadas: 227 registros.
	- Coincidencia `extensions_pbx` vs `lineas_telefonicas`: 227 registros.
	- Autoasignacion resolviendo la primera libre: `1000`.
	- Captura manual valida: `1001`.
	- Captura manual invalida de prueba (`L9001E2E`) rechazada correctamente.
- Depuracion de BD completada:
	- No se encontraron tablas o vistas temporales activas en `database_manager` ni en `registro_agentes`.
	- Se eliminaron 4 lineas residuales de prueba `temp e2e` / `e2e-lada` en `database_manager.lineas_telefonicas`.
	- Conteo final de rastros temporales en `lineas_telefonicas`: `0`.
- Verificacion final del backend: `8/8` pruebas pasadas en `backend/verify_system.py`.

## Cierre complementario UI + ladas (2026-03-22)
- Se reemplazo el formulario de creacion/reactivacion manual de lineas en Altas por una accion explicita de sincronizacion (`Sincronizar Lineas PBX`).
- Se removio el control redundante `Aplicar Filtro` para lineas y el filtro por lada ahora refresca automaticamente al cambiar seleccion.
- Se mantuvo la gestion de `numero_voip` en flujos donde si tiene uso operativo (edicion/cobranza/QR), pero ya no se usa el campo de tipo de linea en Altas.
- Validacion tecnica posterior al ultimo parche:
	- `backend/verify_system.py`: `8/8` pruebas pasadas.
	- Sincronizacion de inventario: `source=227`, `created=0`, `updated=0`, `deactivated=0`.
	- Sincronizacion de ladas: `ladas_created=16`, `ladas_reactivated=0`.
	- `database_manager.ladas_catalogo` activas tras sync: `17`.
	- Rastros temporales en `database_manager.lineas_telefonicas`: `TEMP_ROWS=0`.
	- Lineas gestionadas sincronizadas (`EXT_PBX` + descripcion sync): `227`.
- Nota de validacion API:
	- Las rutas protegidas de lineas/sync responden `403 Not authenticated` sin token en smoke test con `TestClient`, comportamiento esperado por seguridad.