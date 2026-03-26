# CHECKPOINT OPERATIVO 2026-03-25 - Recibos Multiimpresion 3 por Hoja

## Objetivo
Ajustar impresion multiple de recibos para manejar 3 por hoja como predeterminado.

## Cambio aplicado
- `web/js/main.js`
  - Selector en UI para `Recibos por hoja` con opciones 2, 3 y 4.
  - Valor por defecto configurado en 3.
  - Impresion multiple agrupa recibos por pagina respetando el valor seleccionado.
  - Layout de impresion ajusta columnas y altura minima por recibo segun cantidad por hoja.

## Validacion
- `tests/test_sin_linea_e2e.py` -> 43 passed

## Resultado
La reimpresion multiple queda operativa con 3 recibos por hoja por defecto y posibilidad de cambiar a 2 o 4 segun necesidad operativa.
