# Database Manager Server Changelog

Acceso previsto solo desde la maquina servidor mediante la API interna de versionado.

## 1.5.0-rev11 - 2026-04-08
- `detect_header_row`: detecta automaticamente la fila real de cabecera en Excel con etiquetas de categoria en la primera fila.
- `infer_from_values`: infiere campo canonico a partir de valores en la columna (email, telefono, IMEI, deuda, nombre, ubicacion, etc.).
- `ProfileStore`: aprende y reutiliza mapeos confirmados almacenados en `mapping_profiles.json` (clave SHA-1 por conjunto de cabeceras).
- `detect_table_regions`: detecta multiples tablas en la misma hoja separadas por filas en blanco.
- `suggest_mapping_advanced`: combina sinonimo, patron de valor y perfil guardado con 6 niveles de decision; incluye campo `evidencia`.
- Se agregan `fcc`, `imei`, `deuda` y `extension` al catalogo FIELD_SYNONYMS y a CANONICAL_FIELDS del frontend.
- API `analyze/preview/execute` aceptan `header_fila`; `execute` guarda perfil de mapeo al completar importacion exitosa.
- UI muestra fila de encabezado detectada, badges por tipo (valor_patron/perfil_guardado/combinado) y alerta de tablas multiples.

## 1.5.0-rev10 - 2026-04-07
- Se agregan guardas de carrera en `startWebQrScanner`/`stopWebQrScanner` para evitar arranques duplicados.
- Carga dinamica de html5-qrcode con fallback a CDN secundaria si la primera falla.
- Sesion Android usa `sessionStorage` para tokens: las credenciales no persisten entre reinicios de la app nativa.
- Fix en `smartImportSetTab`: la pestana "Inteligente" ahora se activa correctamente al hacer clic.
- Preview del importador inteligente muestra comparacion campo a campo: valor actual vs nuevo.
- Execute del importador admite rollback automatico transaccional al detectar cualquier error parcial.

## 1.5.0-rev9 - 2026-04-07
- Se mejora la barra de contexto de QR/Cobros con campos mas grandes, mejor jerarquia visual y mejor lectura en mobile.
- Se agrega una guia basica de cobros en la pestaña de pago para reducir dudas operativas recurrentes.
- Se habilita busqueda unificada de agentes por nombre, ID o FP sin atajos ambiguos en entradas numericas.
- El endpoint `/api/qr/agentes` agrega coincidencia explicita por `id` y expone `fp` como metadato de respuesta.
- Se valida la regresion del bloque de busqueda/VoIP de agentes QR con pruebas automatizadas en verde.

## 1.5.0-rev8 - 2026-04-07
- Se valida en entorno real la regresion prioritaria del flujo de lineas: 5 pruebas objetivo en verde con Python 3.14.
- Se endurece frontend web para normalizar `linea_id` y bloquear acciones cuando el dato no es consistente.
- API client agrega guardia transversal para evitar endpoints malformados con segmentos `undefined`, `null` o `nan`.
- Mobile valida `agenteId` positivo antes de consultar resumen de pago y evita requests inconsistentes.
- Se agrega paginacion segura a listados de agentes/QR/recibos y se optimiza la sincronizacion de inventario de lineas/ladas.
- Se reconstruye y revalida el bloque publico de verificacion QR para dejar el modulo limpio tras la refactorizacion.

## 1.5.0-rev7 - 2026-04-03
- Se corrige el flujo de "Liberar líneas" en Cambios y Bajas para evitar requests con `linea_id=undefined`.
- Se normaliza resolucion de ID de linea en frontend (`id`, `linea_id`, `linea.id`) con validacion previa.
- API client incorpora guardas reutilizables de IDs positivos para operaciones de lineas (asignar/liberar/editar/desactivar).
- Backend expone lineas activas con ambos campos `id` y `linea_id` para compatibilidad de consumidores.
- Se agrega validacion robusta de `agente_id` en `/api/qr/lineas/{linea_id}/liberar` y regresiones E2E del flujo.

## 1.5.0-rev6 - 2026-03-28
- Se implementa mini-IA para importacion inteligente con conciliacion de agentes por email/telefono/alias/nombre/VOIP.
- Preview de importacion agrega diagnostico operativo (datos de prueba, incoherencias y riesgos priorizados alto/medio/bajo).
- Execute requiere confirmacion explicita y agrega modo estricto para bloquear todo el lote ante conflictos de linea.
- Se integra plan de linea por fila (sin cambio, crear+asignar, reasignar, conflicto) con trazabilidad en respuesta.
- Validacion de cierre en verde: pruebas smart-import, E2E operativa y suite de flujo movil/offline.

## 1.5.0-rev5 - 2026-03-23
- Se agrega seccion exclusiva de Gestion de Lineas con alta/edicion y tabla dedicada.
- Se habilita actualizacion de lineas por API y soporte de lineas manuales fuera de extensions_pbx.
- Se corrige UX de botones QR para abrir vista modal consistente en secciones operativas.
- Se agrega fallback seguro para sincronizacion PBX cuando la tabla legacy no esta disponible.
- Validacion final: suite completa en verde (45 passed) y prueba debug de flujo de lineas.

## 1.5.0-rev4 - 2026-03-23
- Se formaliza cierre limpio del bloque de cambios operativos para cobro por linea y estado consolidado.
- Se verifica entorno de ejecucion con Python 3.14 y dependencias completas en servidor local.
- Suite de validacion ejecutada en verde: 44 pruebas aprobadas.
- Se registra trazabilidad tecnica de cierre en checkpoint del mismo dia.

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
