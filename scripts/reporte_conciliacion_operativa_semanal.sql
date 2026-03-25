-- Reporte de conciliacion operativa semanal
-- Objetivo: cruzar pagos_semanales vs cobros_movimientos y saldo calculado acumulado.
-- Base obligatoria del proyecto:
USE `database_manager`;

-- Parametros opcionales de auditoria.
SET @fecha_desde = DATE_SUB(CURDATE(), INTERVAL 12 WEEK);
SET @fecha_hasta = CURDATE();
SET @agente_id = NULL;

WITH
params AS (
    SELECT
        COALESCE(
            CAST((SELECT valor FROM config_sistema WHERE clave = 'CUOTA_SEMANAL' LIMIT 1) AS DECIMAL(12,2)),
            300.00
        ) AS cuota_semanal
),
semanas AS (
    SELECT DISTINCT p.agente_id, p.semana_inicio
    FROM pagos_semanales p
    WHERE p.semana_inicio BETWEEN @fecha_desde AND @fecha_hasta

    UNION DISTINCT

    SELECT DISTINCT c.agente_id, c.semana_inicio
    FROM cobros_movimientos c
    WHERE c.semana_inicio IS NOT NULL
      AND c.semana_inicio BETWEEN @fecha_desde AND @fecha_hasta
),
semanas_filtradas AS (
    SELECT s.agente_id, s.semana_inicio
    FROM semanas s
    WHERE (@agente_id IS NULL OR s.agente_id = @agente_id)
),
lineas_facturables AS (
    SELECT
        sf.agente_id,
        sf.semana_inicio,
        COUNT(*) AS lineas_activas_semana,
        SUM(
            CASE
                WHEN a.cobro_desde_semana IS NOT NULL
                     AND DATE_SUB(a.cobro_desde_semana, INTERVAL WEEKDAY(a.cobro_desde_semana) DAY) = sf.semana_inicio
                THEN COALESCE(a.cargo_inicial, 0)
                ELSE 0
            END
        ) AS cargo_inicial_semana
    FROM semanas_filtradas sf
    JOIN agente_linea_asignaciones a
      ON a.agente_id = sf.agente_id
     AND COALESCE(a.es_activa, 1) = 1
     AND DATE_SUB(COALESCE(a.cobro_desde_semana, DATE(a.fecha_asignacion), sf.semana_inicio),
                  INTERVAL WEEKDAY(COALESCE(a.cobro_desde_semana, DATE(a.fecha_asignacion), sf.semana_inicio)) DAY) <= sf.semana_inicio
     AND (a.fecha_liberacion IS NULL OR DATE(a.fecha_liberacion) >= sf.semana_inicio)
    JOIN lineas_telefonicas l
      ON l.id = a.linea_id
     AND COALESCE(l.es_activa, 1) = 1
    GROUP BY sf.agente_id, sf.semana_inicio
),
pagos AS (
    SELECT
        p.agente_id,
        p.semana_inicio,
        ROUND(SUM(COALESCE(p.monto, 0)), 2) AS monto_pagado_semana,
        MAX(COALESCE(p.pagado, 0)) AS pagado_semana_flag,
        MAX(p.fecha_pago) AS ultima_fecha_pago
    FROM pagos_semanales p
    WHERE p.semana_inicio BETWEEN @fecha_desde AND @fecha_hasta
      AND (@agente_id IS NULL OR p.agente_id = @agente_id)
    GROUP BY p.agente_id, p.semana_inicio
),
movimientos AS (
    SELECT
        c.agente_id,
        c.semana_inicio,
        ROUND(SUM(CASE WHEN c.tipo_movimiento IN ('ABONO_INICIAL', 'ABONO', 'LIQUIDACION', 'EDICION_PAGO')
                       THEN COALESCE(c.monto, 0)
                       ELSE 0 END), 2) AS neto_mov_pagos_semana,
        ROUND(SUM(CASE WHEN c.tipo_movimiento = 'AJUSTE_DEUDA'
                       THEN COALESCE(c.monto, 0)
                       ELSE 0 END), 2) AS ajuste_deuda_semana,
        COUNT(*) AS movimientos_semana
    FROM cobros_movimientos c
    WHERE c.semana_inicio IS NOT NULL
      AND c.semana_inicio BETWEEN @fecha_desde AND @fecha_hasta
      AND (@agente_id IS NULL OR c.agente_id = @agente_id)
    GROUP BY c.agente_id, c.semana_inicio
),
base AS (
    SELECT
        sf.agente_id,
        ao.nombre,
        sf.semana_inicio,
        COALESCE(lf.lineas_activas_semana, 0) AS lineas_activas_semana,
        COALESCE(lf.cargo_inicial_semana, 0) AS cargo_inicial_semana,
        ROUND((COALESCE(lf.lineas_activas_semana, 0) * (SELECT cuota_semanal FROM params)) + COALESCE(lf.cargo_inicial_semana, 0), 2) AS deuda_teorica_semana,
        COALESCE(p.monto_pagado_semana, 0) AS monto_pagado_semana,
        COALESCE(p.pagado_semana_flag, 0) AS pagado_semana_flag,
        p.ultima_fecha_pago,
        COALESCE(m.neto_mov_pagos_semana, 0) AS neto_mov_pagos_semana,
        COALESCE(m.ajuste_deuda_semana, 0) AS ajuste_deuda_semana,
        COALESCE(m.movimientos_semana, 0) AS movimientos_semana,
        ROUND(COALESCE(p.monto_pagado_semana, 0) - COALESCE(m.neto_mov_pagos_semana, 0), 2) AS diferencia_pagos_vs_mov
    FROM semanas_filtradas sf
    LEFT JOIN agentes_operativos ao
      ON ao.id = sf.agente_id
    LEFT JOIN lineas_facturables lf
      ON lf.agente_id = sf.agente_id
     AND lf.semana_inicio = sf.semana_inicio
    LEFT JOIN pagos p
      ON p.agente_id = sf.agente_id
     AND p.semana_inicio = sf.semana_inicio
    LEFT JOIN movimientos m
      ON m.agente_id = sf.agente_id
     AND m.semana_inicio = sf.semana_inicio
),
acumulado AS (
    SELECT
        b.*,
        ROUND(
            SUM(b.deuda_teorica_semana + b.ajuste_deuda_semana)
            OVER (PARTITION BY b.agente_id ORDER BY b.semana_inicio),
            2
        ) AS deuda_acumulada_calculada,
        ROUND(
            SUM(b.monto_pagado_semana)
            OVER (PARTITION BY b.agente_id ORDER BY b.semana_inicio),
            2
        ) AS total_abonado_acumulado
    FROM base b
)
SELECT
    a.agente_id,
    a.nombre,
    a.semana_inicio,
    a.lineas_activas_semana,
    a.deuda_teorica_semana,
    a.ajuste_deuda_semana,
    a.monto_pagado_semana,
    a.neto_mov_pagos_semana,
    a.diferencia_pagos_vs_mov,
    a.movimientos_semana,
    a.pagado_semana_flag,
    a.ultima_fecha_pago,
    a.deuda_acumulada_calculada,
    a.total_abonado_acumulado,
    ROUND(GREATEST(a.deuda_acumulada_calculada - a.total_abonado_acumulado, 0), 2) AS saldo_calculado_acumulado,
    CASE
        WHEN ABS(a.diferencia_pagos_vs_mov) > 0.009 THEN 'REVISAR_MOVIMIENTOS'
        WHEN GREATEST(a.deuda_acumulada_calculada - a.total_abonado_acumulado, 0) > 0.009 THEN 'CON_SALDO'
        ELSE 'OK'
    END AS estatus_conciliacion
FROM acumulado a
ORDER BY a.semana_inicio DESC, a.agente_id ASC;

-- Resumen semanal consolidado para auditoria ejecutiva.
WITH
params AS (
    SELECT
        COALESCE(
            CAST((SELECT valor FROM config_sistema WHERE clave = 'CUOTA_SEMANAL' LIMIT 1) AS DECIMAL(12,2)),
            300.00
        ) AS cuota_semanal
),
semanas AS (
    SELECT DISTINCT p.agente_id, p.semana_inicio
    FROM pagos_semanales p
    WHERE p.semana_inicio BETWEEN @fecha_desde AND @fecha_hasta

    UNION DISTINCT

    SELECT DISTINCT c.agente_id, c.semana_inicio
    FROM cobros_movimientos c
    WHERE c.semana_inicio IS NOT NULL
      AND c.semana_inicio BETWEEN @fecha_desde AND @fecha_hasta
),
semanas_filtradas AS (
    SELECT s.agente_id, s.semana_inicio
    FROM semanas s
    WHERE (@agente_id IS NULL OR s.agente_id = @agente_id)
),
pagos AS (
    SELECT
        p.agente_id,
        p.semana_inicio,
        ROUND(SUM(COALESCE(p.monto, 0)), 2) AS monto_pagado_semana
    FROM pagos_semanales p
    WHERE p.semana_inicio BETWEEN @fecha_desde AND @fecha_hasta
      AND (@agente_id IS NULL OR p.agente_id = @agente_id)
    GROUP BY p.agente_id, p.semana_inicio
),
movimientos AS (
    SELECT
        c.agente_id,
        c.semana_inicio,
        ROUND(SUM(CASE WHEN c.tipo_movimiento IN ('ABONO_INICIAL', 'ABONO', 'LIQUIDACION', 'EDICION_PAGO')
                       THEN COALESCE(c.monto, 0)
                       ELSE 0 END), 2) AS neto_mov_pagos_semana,
        ROUND(SUM(CASE WHEN c.tipo_movimiento = 'AJUSTE_DEUDA'
                       THEN COALESCE(c.monto, 0)
                       ELSE 0 END), 2) AS ajuste_deuda_semana
    FROM cobros_movimientos c
    WHERE c.semana_inicio IS NOT NULL
      AND c.semana_inicio BETWEEN @fecha_desde AND @fecha_hasta
      AND (@agente_id IS NULL OR c.agente_id = @agente_id)
    GROUP BY c.agente_id, c.semana_inicio
),
lineas_facturables AS (
    SELECT
        sf.agente_id,
        sf.semana_inicio,
        COUNT(*) AS lineas_activas_semana,
        SUM(
            CASE
                WHEN a.cobro_desde_semana IS NOT NULL
                     AND DATE_SUB(a.cobro_desde_semana, INTERVAL WEEKDAY(a.cobro_desde_semana) DAY) = sf.semana_inicio
                THEN COALESCE(a.cargo_inicial, 0)
                ELSE 0
            END
        ) AS cargo_inicial_semana
    FROM semanas_filtradas sf
    JOIN agente_linea_asignaciones a
      ON a.agente_id = sf.agente_id
     AND COALESCE(a.es_activa, 1) = 1
     AND DATE_SUB(COALESCE(a.cobro_desde_semana, DATE(a.fecha_asignacion), sf.semana_inicio),
                  INTERVAL WEEKDAY(COALESCE(a.cobro_desde_semana, DATE(a.fecha_asignacion), sf.semana_inicio)) DAY) <= sf.semana_inicio
     AND (a.fecha_liberacion IS NULL OR DATE(a.fecha_liberacion) >= sf.semana_inicio)
    JOIN lineas_telefonicas l
      ON l.id = a.linea_id
     AND COALESCE(l.es_activa, 1) = 1
    GROUP BY sf.agente_id, sf.semana_inicio
),
base AS (
    SELECT
        sf.agente_id,
        sf.semana_inicio,
        ROUND((COALESCE(lf.lineas_activas_semana, 0) * (SELECT cuota_semanal FROM params)) + COALESCE(lf.cargo_inicial_semana, 0), 2) AS deuda_teorica_semana,
        COALESCE(p.monto_pagado_semana, 0) AS monto_pagado_semana,
        COALESCE(m.neto_mov_pagos_semana, 0) AS neto_mov_pagos_semana,
        COALESCE(m.ajuste_deuda_semana, 0) AS ajuste_deuda_semana,
        ROUND(COALESCE(p.monto_pagado_semana, 0) - COALESCE(m.neto_mov_pagos_semana, 0), 2) AS diferencia_pagos_vs_mov
    FROM semanas_filtradas sf
    LEFT JOIN lineas_facturables lf
      ON lf.agente_id = sf.agente_id
     AND lf.semana_inicio = sf.semana_inicio
    LEFT JOIN pagos p
      ON p.agente_id = sf.agente_id
     AND p.semana_inicio = sf.semana_inicio
    LEFT JOIN movimientos m
      ON m.agente_id = sf.agente_id
     AND m.semana_inicio = sf.semana_inicio
),
acumulado AS (
    SELECT
        b.*,
        ROUND(
            SUM(b.deuda_teorica_semana + b.ajuste_deuda_semana)
            OVER (PARTITION BY b.agente_id ORDER BY b.semana_inicio),
            2
        ) AS deuda_acumulada_calculada,
        ROUND(
            SUM(b.monto_pagado_semana)
            OVER (PARTITION BY b.agente_id ORDER BY b.semana_inicio),
            2
        ) AS total_abonado_acumulado
    FROM base b
),
detalle AS (
    SELECT
        a.semana_inicio,
        a.diferencia_pagos_vs_mov,
        ROUND(GREATEST(a.deuda_acumulada_calculada - a.total_abonado_acumulado, 0), 2) AS saldo_calculado_acumulado,
        CASE
            WHEN ABS(a.diferencia_pagos_vs_mov) > 0.009 THEN 'REVISAR_MOVIMIENTOS'
            WHEN GREATEST(a.deuda_acumulada_calculada - a.total_abonado_acumulado, 0) > 0.009 THEN 'CON_SALDO'
            ELSE 'OK'
        END AS estatus_conciliacion
    FROM acumulado a
)
SELECT
    semana_inicio,
    COUNT(*) AS agentes_revisados,
    SUM(CASE WHEN estatus_conciliacion = 'OK' THEN 1 ELSE 0 END) AS agentes_ok,
    SUM(CASE WHEN estatus_conciliacion = 'CON_SALDO' THEN 1 ELSE 0 END) AS agentes_con_saldo,
    SUM(CASE WHEN estatus_conciliacion = 'REVISAR_MOVIMIENTOS' THEN 1 ELSE 0 END) AS agentes_con_diferencia,
    ROUND(SUM(diferencia_pagos_vs_mov), 2) AS delta_total_pagos_vs_mov,
    ROUND(SUM(saldo_calculado_acumulado), 2) AS saldo_total_calculado
FROM detalle
GROUP BY semana_inicio
ORDER BY semana_inicio DESC;