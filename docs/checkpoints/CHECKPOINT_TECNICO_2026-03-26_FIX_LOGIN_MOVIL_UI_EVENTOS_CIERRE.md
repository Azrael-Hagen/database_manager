# CHECKPOINT TECNICO — 2026-03-26 — Cierre fix login movil UI/eventos

## Incidencias reportadas
1. En Chrome (Android/PC) la vista movil `/m` no iniciaba sesion.
2. Botones `Escritorio` y `Salir` no respondian.
3. Diferencias visibles entre clientes por estructura HTML inconsistente.

## Causas raiz
1. `web/m/mobile.js` no ejecutaba `bindEvents()` en el bootstrap.
   - Resultado: login form y botones principales sin listeners.
2. `web/m/index.html` tenia estructura invalida:
   - `bottomNav` duplicado/anidado.
   - bloques de banner/modal dentro de nav.
3. Orden de scripts no robusto para dependencias offline.

## Cambios aplicados
- `web/m/mobile.js`
  - Se invoca `bindEvents()` durante bootstrap.
  - Se agrego handler para `syncNowBtn` con flujo seguro de sync manual.
- `web/m/index.html`
  - Se elimino duplicacion/anidacion de `bottomNav`.
  - Se reubicaron `syncStatusBanner` y `offlineConflictModal` fuera de `nav`.
  - Se ajusto orden de scripts: librerias offline antes de `mobile.js`.
- `tests/test_api.py`
  - Se corrigio seccion rota (IndentationError).
  - Se agregaron pruebas de regresion para ruta `/m`:
    - botones `switchDesktopBtn`/`logoutBtn` presentes,
    - `bottomNav` unico,
    - orden de scripts de modulos offline antes de `mobile.js`.

## Validacion
### Pruebas automatizadas
- `pytest tests/test_api.py -k "health_check or mobile_route"` -> `4 passed`
- `pytest tests/test_https_redirect.py` -> `5 passed`

### E2E auth/network
- `E2E_IP_LOGIN_OK:True`
- `E2E_DOMAIN_HTTP_REDIRECT:307 -> https://phantom.database.net/api/auth/login`
- `E2E_DOMAIN_HTTPS_LOGIN_OK:True`

## Estado
COMPLETADO
