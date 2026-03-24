# CHECKPOINT OPERATIVO — 2026-03-24 — Alertas, Roles y Rendimiento

## Estado previo detectado
- Envío de alertas del sistema restringido a `super_admin` (backend + UI), lo que bloquea operación en instalaciones que usan roles visibles `viewer/capture/admin`.
- UI de usuarios muestra solo 3 roles en selector (`viewer`, `capture`, `admin`), aunque backend soporta 4 (`super_admin` incluido).
- Sección Alertas carga sin filtros finos y renderiza todo en cada refresco manual.

## Objetivos del bloque
1. Habilitar envío de alertas para `admin` y `super_admin`.
2. Exponer y describir claramente los 4 roles actuales y capacidades.
3. Mejorar UX visual de Alertas (filtros + resumen) y funcionalidad.
4. Aplicar mejora de rendimiento en flujo de alertas (menos payload/render innecesario).

## Archivos previstos
- backend/app/api/alertas.py
- backend/app/api/usuarios.py
- tests/test_api.py
- web/index.html
- web/js/main.js
- web/css/style.css

## Validación prevista
- Pruebas API para permisos de alertas
- Pruebas API para endpoint de capacidades de roles
- Validación manual UI (panel roles + filtros alertas)
