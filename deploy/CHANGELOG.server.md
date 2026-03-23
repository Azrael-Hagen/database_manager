# Database Manager Server Changelog

Acceso previsto solo desde la maquina servidor mediante la API interna de versionado.

## 1.5.0-rev1 - 2026-03-23
- Se define `start.bat` como script oficial de arranque del servidor.
- `start_easy.bat` queda como lanzador UX y se elimina el wrapper redundante del backend.
- Los QR de agentes quedan estaticos por agente usando URL publica estable por UUID.
- La validacion del QR ya no depende de un token efimero ni de la linea incrustada en el codigo; el servidor consulta el estado actual del agente y su linea activa.
- Se agrega exportacion PDF por lotes para impresion en hoja o etiquetas.
- Se agrega registro formal de version y revision con endpoint visible solo desde el servidor.
- Se conservan las mejoras recientes de alertas de sistema, SIN LINEA, dashboard y correcciones de suite.
