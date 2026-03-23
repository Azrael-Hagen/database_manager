# Database Manager Server Changelog

Acceso previsto solo desde la maquina servidor mediante la API interna de versionado.

## 1.5.0-rev3 - 2026-03-23
- Se aplica flujo operativo de cobro por línea activa por semana ($300 MXN por línea configurable desde cuota base).
- Se integra captura de primer cobro en asignaciones iniciales (semana de inicio y/o cargo inicial).
- Se habilita filtro de líneas por estado (todas, libres, ocupadas) en Altas de Agentes.
- Estado de Agentes queda consolidado por agente (una fila), mostrando conteo y lista de líneas activas.
- Se ajusta verificación QR para exponer tarifa por línea, líneas activas y cargo semanal total por agente.
- Validación de limpieza: dependencias instaladas y pruebas en verde (44 passed).

## 1.5.0-rev2 - 2026-03-23
- Se agrega depuracion automatica de agentes redundantes al arranque (configurable con `AUTO_AGENT_DATA_CLEANUP_ON_STARTUP`).
- Se agrega endpoint de mantenimiento para depurar agentes redundantes con `dry_run`.
- Se corrige Cambios y Bajas para evitar repetir alias dentro del bloque de nombre cuando alias==nombre.
- Se deduplica la vista operativa de agentes por nombre+alias para evitar inconsistencias visuales.
- Se ejecuta limpieza operativa adicional de duplicados por nombre+alias sin referencias (en `database_manager` y espejo `registro_agentes`).

## 1.5.0-rev1 - 2026-03-23
- Se define `start.bat` como script oficial de arranque del servidor.
- `start_easy.bat` queda como lanzador UX y se elimina el wrapper redundante del backend.
- Los QR de agentes quedan estaticos por agente usando URL publica estable por UUID.
- La validacion del QR ya no depende de un token efimero ni de la linea incrustada en el codigo; el servidor consulta el estado actual del agente y su linea activa.
- Se agrega exportacion PDF por lotes para impresion en hoja o etiquetas.
- Se agrega registro formal de version y revision con endpoint visible solo desde el servidor.
- Se conservan las mejoras recientes de alertas de sistema, SIN LINEA, dashboard y correcciones de suite.
