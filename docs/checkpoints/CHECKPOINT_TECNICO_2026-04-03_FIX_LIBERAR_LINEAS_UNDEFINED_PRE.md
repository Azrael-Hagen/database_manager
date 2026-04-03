# CHECKPOINT TECNICO - 2026-04-03 - FIX LIBERAR LINEAS UNDEFINED (PRE)

## Objetivo
Corregir el flujo de "Liberar lineas" en Cambios y Bajas que esta enviando `linea_id=undefined` al endpoint `/api/qr/lineas/{linea_id}/liberar` y revisar otros puntos del flujo de datos relacionados para prevenir IDs invalidos.

## Alcance
- web/js/main.js
- web/js/api-client.js
- backend/app/api/qr.py
- tests asociados al flujo de lineas/Cambios y Bajas

## Criterios de aceptacion
- Nunca se envia `undefined`/`null`/no numerico como `linea_id` al endpoint de liberar.
- El frontend valida y reporta error claro al usuario si no existe ID de linea valido.
- El backend responde de forma robusta ante payload inconsistente sin romper el flujo.
- Pruebas del flujo afectado en verde (unitarias/integracion y validacion operativa).
- Versionado incrementado y changelog actualizado.

## Riesgos
- Diferencia de shape de datos en listas de lineas (id vs linea_id).
- Regresion en otros botones de lineas dentro de Cambios y Bajas o Gestion de Lineas.

## Mitigacion
- Normalizar resolucion de ID de linea en frontend (id/linea_id/linea.id).
- Agregar guardas reutilizables para IDs de linea en llamadas API.
- Cubrir con pruebas negativas de input invalido.
