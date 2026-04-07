# CHECKPOINT TECNICO — 2026-04-07 — UX QR/Cobros + Busqueda FP

## Objetivo
Mejorar usabilidad visual de la barra de contexto en QR y Cobros, reducir ambiguedad en busqueda de agentes (ID/FP), agregar guia basica de cobros y validar flujos web/mobile antes de commit/push.

## Alcance
- Frontend:
  - web/index.html
  - web/css/style.css
  - web/js/qrCobros.js
- Backend:
  - backend/app/api/qr.py (busqueda /api/qr/agentes)
- Tests:
  - tests/test_sin_linea_e2e.py
- Documentacion:
  - docs/GUIA_COBROS_BASICA.md

## Riesgos a controlar
1. Regresion de busqueda por ID en autocompletado.
2. Ruptura visual responsive en la barra de contexto (desktop/mobile).
3. Cambios en query de agentes que afecten rendimiento o resultados.
4. Desincronizacion de campos contexto -> formularios de pago/verificacion.

## Estrategia de mitigacion
- TDD para busqueda de agentes por ID y FP.
- Mantener compatibilidad del payload existente y extender solo donde sea necesario.
- Ajustes CSS con breakpoints existentes y sin alterar flujos validados no relacionados.
- Validacion final con pytest focalizado y verificacion de errores.

## Criterios de salida
- Busqueda por FP funcional desde UI y API.
- Campos de contexto mas legibles/espaciados en desktop y mobile.
- Guia basica de cobros disponible.
- Pruebas relevantes en verde y sin errores nuevos en archivos modificados.

## Ejecucion y resultados
- Backend: `GET /api/qr/agentes` ahora incluye match explicito por `id` numerico y mantiene busqueda por nombre/telefono/datos_adicionales; se agrega `fp` al payload para consumo de UI.
- Frontend: busquedas en contexto QR y deuda manual eliminan atajo numerico ambiguo y usan busqueda unificada por nombre/ID/FP con metadatos visibles de FP.
- UI: se incrementa area util de campos de contexto, se mejora jerarquia de labels y se agrega bloque "Guia basica de cobros" en la tab de Pago.
- Documentacion: se crea `docs/GUIA_COBROS_BASICA.md` con flujo operativo y checklist rapido.

## Validacion
- `PYTHONPATH=backend python -m pytest tests/test_sin_linea_e2e.py::TestQrAgentesBusquedaYVoip -q` -> 4 passed.
- `get_errors` sin errores nuevos en archivos modificados (excepto import resolution esperado por entorno en tests fuera de PYTHONPATH configurado).
