# Checkpoint Operativo — Web Movil Offline Local Cierre

Fecha: 2026-03-26
Estado: Completado

## Resultado del bloque
- La APK ahora carga directamente la vista movil `/m`, no la raiz del sitio.
- El shell movil relevante para la app (`/m`, `mobile.js`, `mobile.css`, libs moviles y `js/api-client.js`) queda cacheable para reutilizacion offline en WebView.
- La web movil guarda snapshots locales de dashboard, pagos, alertas, datos y resumen por agente para render de respaldo cuando falla la conectividad.
- La app Android guarda tambien un snapshot HTML del panel movil dentro de `SessionStore` y lo usa como fallback al recargar o cuando el servidor deja de responder.
- Si existe token y usuario cacheado, la sesion no se invalida solo por perdida de red; la UI intenta operar en modo local.
- La barra superior nativa de Phantom App se compacta y se oculta automaticamente cuando el panel queda listo; reaparece si hay error o si el usuario toca el estado.
- Se corrigio el WebViewClient para no tratar el estado "Conectando con el panel..." como error real; antes eso podia disparar reintentos espurios al recargar.

## Verificacion ejecutada
- `pytest ../tests/test_api.py -q` desde `backend`: 36 pruebas aprobadas.
- `./gradlew.bat testDebugUnitTest` en `Phantom App`: pruebas unitarias Android aprobadas, incluyendo politica de carga y decodificacion del shell HTML offline.

## Riesgos remanentes
- No se ejecuto validacion E2E manual en dispositivo Android real dentro de esta corrida.
- El escaneo por camara web sigue dependiendo del script remoto de `html5-qrcode`; el flujo recomendado dentro de la app sigue siendo el escaneo nativo.

## Notas operativas
- El modo local muestra snapshots previos; no inventa datos nuevos sin backend.
- Los pagos offline siguen persistiendo en IndexedDB y se sincronizan al volver la conectividad.