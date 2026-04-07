# CHECKPOINT TECNICO 2026-04-07 - REPARACION FLUJO LINEAS + AUDITORIA

## Contexto
Se detecto error operativo en produccion: `POST /api/qr/lineas/undefined/liberar` con respuesta 422.
Objetivo: reparar flujo sin romper funcionalidad existente y ejecutar auditoria de BD/performance/utilidad de modulos.

## Fuentes de mejores practicas consultadas
- FastAPI Path Params: https://fastapi.tiangolo.com/tutorial/path-params/
- FastAPI Error Handling: https://fastapi.tiangolo.com/tutorial/handling-errors/
- OWASP API Security Top 10 (2023): https://owasp.org/API-Security/
- MDN Number.isInteger: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Number/isInteger
- SQL indexing guidance: https://use-the-index-luke.com/sql/where-clause/the-equals-operator/concatenated-keys
- Reference architecture: https://github.com/fastapi/full-stack-fastapi-template

## Hallazgos tecnicos
1. El backend ya valida `linea_id` tipado como `int`, por eso `undefined` produce 422 temprano (comportamiento correcto por contrato).
2. El riesgo principal esta en frontend al construir acciones con `linea.id` sin normalizacion central cuando la carga de datos puede traer variantes (`linea_id`, anidado).
3. El cliente API valida IDs en metodos de dominio, pero faltaba una guardia transversal para endpoint malformado desde otros callers.

## Plan de ejecucion (sin romper flujo)
1. TDD: agregar pruebas de regresion para exigir normalizacion de ID y guardia de endpoint.
2. Hardening UI: introducir `resolveLineaId(linea)` y usarlo en listados de lineas para acciones `Liberar/Editar/Desactivar`.
3. Hardening API client: bloquear request si endpoint contiene segmentos `undefined/null/nan`.
4. Validacion: correr pruebas objetivo y revisar errores.
5. Auditoria tecnica:
   - inventario de consultas y puntos de posible indexacion,
   - deteccion rapida de codigo no referenciado/candidatos a modularizacion,
   - riesgos de performance y seguridad.
6. Entrega: resumen de cambios, riesgos y siguientes pasos.

## Criterios de aceptacion
- No se genera llamada a `/api/qr/lineas/undefined/liberar` desde UI actual.
- Se conserva funcionalidad de liberar linea individual y por agente.
- Pruebas de regresion nuevas en verde.
- Se documentan hallazgos de auditoria con acciones concretas.

## Estado
- [x] Plan y checkpoint tecnico creados
- [x] TDD inicial agregado
- [x] Implementacion hardening frontend/api-client
- [x] Mejoras de paginacion y optimizacion SQL de bajo riesgo en QR API
- [x] Hardening mobile para IDs invalidos en carga de resumen de pago
- [x] Validacion final de pruebas
- [x] Auditoria BD/performance/modulos cerrada (analisis estatico)

## Resultado de auditoria (resumen ejecutivo)
1. Riesgo principal corregido: evitar construccion de endpoints con segmentos invalidos (`undefined`, `null`, `nan`) en cliente web.
2. Riesgo de flujo corregido: normalizacion de `linea_id` en render de acciones para evitar botones con IDs inconsistentes.
3. Rendimiento mitigado: en sincronizacion de inventario de lineas se evita cargar catalogos completos cuando basta subconjunto por `IN (...)`.
4. Escalabilidad mejorada: listados masivos QR ahora soportan `skip/limit` sin romper respuesta existente.
5. Mobile robustecido: validacion estricta de `agenteId` antes de solicitar resumen de pago.

## Validacion ejecutada
- Entorno Python configurado: `c:/python314/python.exe`.
- Dependencias backend instaladas desde `backend/requirements.txt`.
- Regresion objetivo ejecutada en verde con `PYTHONPATH=backend`.
- Resultado: `5 passed, 50 deselected in 3.40s`.
