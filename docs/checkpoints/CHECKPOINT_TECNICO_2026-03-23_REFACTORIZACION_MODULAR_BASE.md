# CHECKPOINT TECNICO 2026-03-23 - REFACTORIZACION MODULAR BASE

## Objetivo
Reducir acoplamiento y concentracion excesiva de responsabilidades en backend y frontend, sin romper los flujos ya validados de QR, lineas, dashboard y exportacion.

## Alcance aprobado para este bloque
- Extraer helpers reutilizables de seguridad QR a un servicio dedicado.
- Extraer normalizacion y serializacion de lineas a un servicio dedicado.
- Extraer utilidades UI reutilizables del frontend a un modulo base compartido.
- Mantener compatibilidad retroactiva de nombres/handlers actuales para no romper HTML, eventos ni pruebas existentes.

## Riesgos controlados
- `backend/app/api/qr.py` es un archivo de alta sensibilidad y gran tamaño; los cambios se aplicaran por funciones de soporte, no por rediseño completo de endpoints.
- `web/js/main.js` conserva sus funciones publicas actuales como fachada, aunque deleguen a un modulo nuevo.
- No se modifican contratos REST ni estructuras persistidas en BD en este bloque.

## Validacion prevista
- Pruebas unitarias/funcionales para servicios extraidos.
- Regresion enfocada de assets frontend.
- Regresion QR/lineas/exportacion.
- Si el tiempo de ejecucion lo permite, corrida mas amplia E2E del proyecto.

## Restricciones mantenidas
- La UI solo debe reflejar datos reales de BD/API.
- La base operativa por defecto sigue siendo `database_manager`.
- No se reintroduce el campo Empresa en formularios/tablas de gestion.
