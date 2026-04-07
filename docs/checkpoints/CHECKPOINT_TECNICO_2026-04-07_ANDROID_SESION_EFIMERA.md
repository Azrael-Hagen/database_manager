# CHECKPOINT TECNICO — 2026-04-07 — Android sesion efimera

## Objetivo
Permitir que la app Android conserve credenciales/sesion del cobrador solo mientras la app permanece abierta y evitar persistencia al cerrarla.

## Alcance
- web/js/api-client.js
- web/m/mobile.js
- tests/test_sin_linea_e2e.py

## Riesgos
1. Cierre de sesion involuntario en web desktop.
2. Persistencia cruzada entre localStorage y sessionStorage.
3. Regresiones en boot/login/logout mobile.

## Mitigacion
- Activar modo de persistencia de sesion solo en runtime nativo Android.
- Limpiar token de almacenamiento persistente al entrar en modo nativo.
- Pruebas de regresion por inspeccion de assets (mobile/api-client).

## Criterios de salida
- Sesion movil nativa persiste dentro de la app abierta.
- Sesion no reaparece tras cerrar y abrir app (sin token durable).
- Desktop mantiene comportamiento actual.
