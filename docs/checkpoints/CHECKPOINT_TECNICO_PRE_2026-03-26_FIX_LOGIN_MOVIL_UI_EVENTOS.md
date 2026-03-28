# CHECKPOINT TECNICO PREVIO — 2026-03-26 — Fix login movil y eventos UI

## Objetivo
Corregir fallas en la vista movil `/m` donde no inicia sesion desde Chrome (Android/PC), botones `Escritorio` y `Salir` sin accion, y diferencias de render entre clientes.

## Hallazgos iniciales
1. `web/m/mobile.js` no ejecuta `bindEvents()` en bootstrap; por eso no se enlazan `loginForm`, `switchDesktopBtn` y `logoutBtn`.
2. `web/m/index.html` tiene estructura invalida (navegacion `bottomNav` duplicada/anidada) y mezcla de bloques fuera de lugar.
3. Carga de scripts no robusta para dependencias offline (orden no garantizado para inicializacion).
4. `tests/test_api.py` presenta `IndentationError`, bloqueando validacion automatica.

## Alcance autorizado del bloque
- Ajustar `web/m/index.html` para estructura HTML valida y consistente.
- Ajustar `web/m/mobile.js` para inicializacion correcta de eventos y acciones de sync.
- Corregir `tests/test_api.py` en la seccion movil/sistema para restaurar ejecucion de pytest.

## Criterios de aceptacion
- `/m` renderiza con un solo `bottomNav` y controles esperados.
- Login web movil vuelve a ejecutar flujo de autenticacion en Chrome (PC/Android).
- Botones `Escritorio` y `Salir` responden.
- Pruebas de ruta movil y salud ejecutan en verde.

## Riesgos y mitigacion
- Riesgo: tocar layout movil rompa flujo QR/pagos.
  Mitigacion: cambios quirurgicos, sin alterar IDs usados por JS.
- Riesgo: regresion silenciosa en rutas moviles.
  Mitigacion: agregar asserts de estructura/orden de scripts en pruebas.
