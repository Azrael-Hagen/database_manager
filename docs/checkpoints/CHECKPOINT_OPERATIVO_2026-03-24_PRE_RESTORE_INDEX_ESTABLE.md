# Checkpoint Operativo - 2026-03-24 - Pre Restore index.html

## Contexto
Se detecto corrupcion estructural en `web/index.html` (duplicacion de secciones y mezcla de bloques), incluyendo doble aparicion de `estadoAgentesSection`.

## Verificacion Git
Auditoria de commits recientes sobre `web/index.html`:
- `5c6ee75`: `estadoAgentesSection` duplicado (2 ocurrencias).
- `76e9442`: estructura consistente (1 ocurrencia por seccion critica).

## Decision
Restaurar `web/index.html` desde `76e9442` como baseline estable y re-aplicar mejoras visuales de forma controlada.

## Riesgo mitigado
Evitar seguir parchando sobre HTML inconsistente para prevenir regresiones funcionales en secciones `usuarios`, `auditoria`, `estadoAgentes` y `alertas`.
