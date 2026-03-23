# Checkpoint Técnico - 2026-03-23

## Objetivo
Implementar el bloque operativo solicitado:
- URL LAN con variantes (con puerto y amigable sin puerto cuando aplique).
- Advertencia proactiva de cámara cuando se accede por HTTP no seguro.
- Ciclo de vida de usuarios temporales (máximo 10 días, autoeliminación con historial, renovación y solicitud de permisos).

## Alcance previsto
1. Backend
- Extensión de `usuarios` con metadatos temporales.
- Tabla histórica para temporales eliminados/expirados.
- Mantenimiento automático de expirados.
- Endpoints para crear temporal, renovar, solicitar permisos y consultar historial/solicitudes.

2. Frontend
- Consumo de nuevas propiedades/endpoints de usuarios temporales.
- Render de estado temporal en gestión de usuarios.
- Controles de renovación y solicitud de permisos.
- Aviso visual temprano de requisito HTTPS para cámara.
- Presentación de acceso LAN con URL principal y alternativa amigable.

## Riesgos controlados
- Compatibilidad de datos existentes mediante migración no destructiva.
- Sin cambios en flujos validados fuera del alcance.
- Sin modificación de tablas operativas de agentes/pagos ya validadas.
