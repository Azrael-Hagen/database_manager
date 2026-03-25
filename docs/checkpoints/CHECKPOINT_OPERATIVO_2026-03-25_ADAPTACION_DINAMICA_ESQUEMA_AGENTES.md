# CHECKPOINT OPERATIVO 2026-03-25 - Adaptacion dinamica de esquema de agentes

## Contexto
Se detectaron fallos de arranque cuando se eliminaron columnas opcionales de `agentes_operativos` (ej. `telefono`, `email`, `datos_adicionales`) y las vistas del bootstrap seguian referenciandolas de forma fija.

## Cambios aplicados
- Archivo ajustado: `backend/app/database/orm.py`.
- Se elimino la recreacion forzada de columnas en `agentes_operativos`.
- Se incorporo lectura dinamica de columnas reales desde `information_schema`.
- Se implemento generacion dinamica de SQL para:
  - `vw_agentes_qr_estado`
  - `vw_agentes_extensiones_pago_actual`
  - `vw_agentes_operacion_actual`
- Cuando una columna no existe, las vistas ahora usan valores seguros (`NULL`, `0`, `''`, `1`) y evitan joins incompatibles.
- La creacion de indices sobre `agentes_operativos` ahora se condiciona a la existencia de las columnas requeridas.

## Validacion
- Pruebas ejecutadas:
  - `python -m pytest tests/test_schema_updates.py -q` -> 3 passed
- Smoke test de arranque:
  - Startup completo antes del conflicto de puerto (proceso concurrente en 8000).
  - `GET /api/health` respondio OK en instancia activa.

## Resultado
El servidor ya no depende de que existan columnas opcionales eliminadas en `agentes_operativos` para iniciar y construir vistas.
