# Checkpoint Técnico — Web Móvil Robusto

Fecha: 2026-03-26
Estado: En progreso

## Objetivo
- Crear una versión móvil dedicada del panel web usando la API existente.
- Habilitar apertura automática de esa versión en dispositivos móviles.
- Mantener compatibilidad total con escritorio y sin alterar flujos validados del backend.

## Alcance
- Ruta móvil dedicada (`/m` y `/mobile`).
- UI móvil completa (login, dashboard, QR manual, datos paginados).
- Navegación móvil tipo tabs con acciones de sesión.
- Conmutación explícita entre vista móvil y escritorio.

## Riesgos y mitigación
- Riesgo: redirección no deseada en escritorio.
  Mitigación: detección por user-agent + ancho + override por query/localStorage.
- Riesgo: romper layout existente.
  Mitigación: archivos móviles aislados en carpeta `web/m/`.
- Riesgo: degradación en red móvil.
  Mitigación: carga paginada y operaciones acotadas en vista de datos.