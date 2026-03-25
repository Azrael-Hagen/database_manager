# CHECKPOINT OPERATIVO 2026-03-25 - Persistencia Cobros/QR y Unificacion de Vistas

## Objetivo del bloque
Asegurar que pagos, cobros y ajustes de deuda queden persistidos en base de datos sin depender de estado en memoria o solo de archivos, y reducir redundancia de vistas SQL para evitar derivas funcionales.

## Cambios aplicados
- `backend/app/api/qr.py`
  - Persistencia adicional de QR en `agentes_operativos.qr_code` (blob) al regenerar QR.
  - Registro de historial de movimientos de cobro en tabla `cobros_movimientos` para:
    - abonos iniciales/abonos
    - liquidaciones
    - ediciones administrativas de pago
    - ajustes manuales de deuda
  - Optimización de consultas de totales (`/api/qr/pagos/totales`) usando rangos de fecha (sin `DATE(col)` en filtros), habilitando uso de índices.
- `backend/app/database/orm.py`
  - Nueva tabla `cobros_movimientos` en bootstrap de esquema.
  - Índices nuevos en `pagos_semanales`:
    - `ix_pagos_semanales_fecha_pago_monto`
    - `ix_pagos_semanales_semana_monto`
  - Unificación de creación de vistas útiles con origen único dinámico:
    - `vw_agentes_qr_estado`
    - `vw_usuarios_roles`
    - `vw_pagos_pendientes`
    - `vw_agentes_extensiones_pago_actual`
    - `vw_agentes_operacion_actual`
- `backend/app/api/database.py`
  - Endpoint de mantenimiento de vistas ahora usa mapa central dinámico desde ORM (`get_useful_views_sql_map`).
- `tests/test_schema_updates.py`
  - Pruebas para validar mapa unificado de vistas y tolerancia dinámica de columnas.

## Validaciones
- Pruebas:
  - `tests/test_schema_updates.py` -> OK
  - `tests/test_sin_linea_e2e.py` (casos de totales y export QR) -> OK
  - `tests/test_api.py` (subset crítico) -> OK
  - `tests/test_smart_export.py` -> OK
- Esquema:
  - Tabla `cobros_movimientos` creada en BD activa.
  - Vistas clave presentes.
- Rendimiento:
  - `EXPLAIN` de agregación por fecha en `pagos_semanales` pasó de `type=ALL` a `type=range` usando índice `ix_pagos_semanales_fecha_pago_monto`.

## Resultado
Se refuerza durabilidad de datos operativos (cobros/deuda/QR), se reduce redundancia de definición de vistas y se mejora eficiencia de consultas de totales de cobranza.
