# Checkpoint Técnico — Phantom App QR Nativo

Fecha: 2026-03-25
Estado: En progreso

## Objetivo
- Eliminar la dependencia del escaneo QR vía `getUserMedia` dentro del WebView cuando el servidor corre por HTTP LAN.
- Mantener la validación y operación de cobros en el backend/web actual.

## Decisiones
- Usar CameraX para preview estable entre dispositivos.
- Usar ML Kit con modelo empaquetado para lectura inmediata sin descarga diferida.
- Restringir permisos WebView al origen exacto del servidor descubierto/guardado.
- Inyectar el código escaneado al flujo web existente en lugar de duplicar la lógica de negocio en Android.

## Riesgos y mitigación
- HTTP inseguro bloquea cámara web: mitigado con escáner nativo.
- Navegación a orígenes no confiables en WebView: mitigado con política de mismo origen y apertura externa.
- Permisos de cámara inconsistentes: mitigado con solicitud runtime única y concesión controlada.
- Modelos descargables con latencia inicial: mitigado usando ML Kit empaquetado.