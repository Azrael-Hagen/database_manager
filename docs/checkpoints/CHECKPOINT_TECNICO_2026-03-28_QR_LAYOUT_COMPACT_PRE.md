# CHECKPOINT TECNICO — 2026-03-28 — QR Layout Compact (PRE)

## Objetivo del bloque
- Reducir espacio en blanco desperdiciado en etiquetas PDF de QR.
- Mantener tamano operativo de etiqueta/QR, incrementando aprovechamiento visual en carta/oficio.
- Reemplazar el editor actual por controles simples y utiles para operacion.

## Estado antes del cambio
- Endpoint activo: `GET /api/qr/agentes/export/pdf` con layouts `sheet|labels|oficio`.
- Motor actual: `backend/app/utils/qr_print.py`.
- UI actual de exportacion incluye editor libre de parametros en `web/index.html` + `web/js/main.js`.
- Prueba E2E existente valida solo que el PDF se genera para `labels` y `oficio`.

## Riesgos identificados
- Regresion visual de densidad por cambios en calculo de caja interna.
- Incompatibilidad de overrides al simplificar el editor.
- Alterar funcionalidad validada de exportacion por lotes o marcado de impresos.

## Estrategia de implementacion
1. Agregar pruebas unitarias para layout/compactacion en `qr_print`.
2. Ajustar algoritmo de render para minimizar caja inutil dentro de cada celda sin cambiar pagina/rows/columns.
3. Simplificar editor de UI a presets de compactacion por layout y mantener compatibilidad de parametros backend.
4. Ejecutar pruebas objetivo (unit + e2e export PDF).

## Criterios de aceptacion
- PDF generado en carta/oficio sin errores.
- Etiquetas mantienen tamano operativo y reducen espacio en blanco interno.
- UI deja de exponer parametros complejos no utiles y ofrece opciones claras.
- Sin regresion en flujo de exportar/marcar impresos.
