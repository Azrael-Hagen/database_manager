# CHECKPOINT TECNICO - 2026-03-23 (Consistencia Cambios/Bajas + Version rev2)

## Objetivo
Corregir inconsistencias visuales y de datos en Cambios y Bajas, eliminar duplicados persistentes y dejar versionado/documentacion alineados.

## Problemas detectados
1. En Cambios/Bajas seguian apareciendo duplicados (ejemplo: Barbas repetido en multiples IDs).
2. En UI se repetia alias dentro del bloque de nombre aunque `alias == nombre`.
3. Version/changelog/README no reflejaban aun la depuracion automatizada y ajustes operativos recientes.

## Cambios aplicados
1. UI Cambios/Bajas
- Se ajusta etiqueta de identidad para no repetir alias cuando coincide con nombre.
- Se deduplica la lista operativa por `nombre+alias` para visualizacion/operacion consistente.
- Se aplica la misma deduplicacion al selector de agentes en flujo de asignacion.

2. Backend depuracion
- Se amplian candidatos de limpieza para incluir duplicados por `nombre+alias` (ademas de firma completa), siempre sin referencias operativas.

3. Limpieza ejecutada en BD
- Se eliminaron duplicados adicionales por `nombre+alias` sin referencias.
- Resultado:
  - candidatos eliminados en corrida adicional: 47
  - agentes activos post-limpieza: 149
  - ejemplo `Barbas` post-limpieza: 1 registro activo
- Se sincronizo eliminacion contra `registro_agentes.agentes` por ID.

4. Version y revision
- `deploy/version-info.json` actualizado a `1.5.0-rev2`.
- `deploy/CHANGELOG.server.md` actualizado con entrada `1.5.0-rev2`.

5. Documentacion
- `README.md` actualizado con seccion de depuracion de agentes redundantes y bandera `AUTO_AGENT_DATA_CLEANUP_ON_STARTUP`.

## Verificacion
- Suite completa: 44 passed.
- Sin errores de sintaxis en archivos modificados.
