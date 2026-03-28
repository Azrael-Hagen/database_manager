# Checkpoint Operativo — Web Movil Offline Local Previo

Fecha: 2026-03-26
Estado: Previo

## Objetivo del bloque
- Mantener operativa la vista movil dentro de la app Android aun cuando el servidor o la red dejen de estar disponibles temporalmente.
- Persistir una version local util del estado operativo para no dejar la UI vacia sin conectividad.
- Reducir la friccion visual del contenedor Android ocultando controles de descubrimiento cuando ya existe una sesion cargada.

## Hallazgos confirmados
- La web movil persiste pagos offline en IndexedDB, pero no guarda snapshots de dashboard, pagos, alertas ni datos para render offline.
- La app Android carga el origen base descubierto, no la ruta movil dedicada `/m`.
- El servidor entrega `/m`, `mobile.js`, `mobile.css` y librerias moviles con `Cache-Control: no-store`, lo que impide reutilizar el shell en el WebView cuando falta red.
- El contenedor Android deja visibles los controles superiores aun despues de conectar, especialmente el boton de deteccion de servidor.

## Riesgos y mitigacion
- Riesgo: servir cache movil demasiado agresivo y dejar shell desactualizado.
  Mitigacion: usar cache privado de corta vida con `stale-while-revalidate`, limitado solo a assets del shell movil.
- Riesgo: abrir datos obsoletos sin advertencia.
  Mitigacion: snapshots con timestamp y mensajes explicitos de modo local.
- Riesgo: romper navegacion validada fuera de la app.
  Mitigacion: limitar cambios de UI nativa al proyecto Android y mantener contratos backend/API intactos.

## Criterios de aceptacion del bloque
- La vista `/m` y sus assets base quedan cacheables para reutilizacion offline en el WebView.
- La web movil puede renderizar dashboard, pagos, alertas y datos desde snapshot local cuando falla la red.
- Si existe token y usuario cacheado, la app no expulsa la sesion solo por falta de conectividad.
- La app Android carga directamente la ruta movil y esconde la barra superior cuando el panel ya esta listo.