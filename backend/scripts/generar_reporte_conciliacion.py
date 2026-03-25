"""Automatizador de reporte de conciliacion operativa semanal.

Genera archivos CSV/JSON usando las mismas reglas de conciliacion de pagos,
movimientos y saldo calculado acumulado.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text


# Permite importar app.config al ejecutar desde backend/scripts
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import config  # noqa: E402


REPORT_DIR = Path(__file__).resolve().parents[2] / "logs" / "reportes_conciliacion"


BASE_CTE = """
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
    WHERE p.semana_inicio BETWEEN :fecha_desde AND :fecha_hasta

    UNION DISTINCT

    SELECT DISTINCT c.agente_id, c.semana_inicio
    FROM cobros_movimientos c
    WHERE c.semana_inicio IS NOT NULL
      AND c.semana_inicio BETWEEN :fecha_desde AND :fecha_hasta
),
semanas_filtradas AS (
    SELECT s.agente_id, s.semana_inicio
    FROM semanas s
    WHERE (:agente_id IS NULL OR s.agente_id = :agente_id)
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
    WHERE p.semana_inicio BETWEEN :fecha_desde AND :fecha_hasta
      AND (:agente_id IS NULL OR p.agente_id = :agente_id)
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
      AND c.semana_inicio BETWEEN :fecha_desde AND :fecha_hasta
      AND (:agente_id IS NULL OR c.agente_id = :agente_id)
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
"""


DETAIL_QUERY = (
    BASE_CTE
    + """
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
ORDER BY a.semana_inicio DESC, a.agente_id ASC
"""
)


SUMMARY_QUERY = (
    BASE_CTE
    + """
,detalle AS (
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
ORDER BY semana_inicio DESC
"""
)


@dataclass(frozen=True)
class ReportParams:
    fecha_desde: date
    fecha_hasta: date
    agente_id: int | None


def _parse_date(raw: str) -> date:
    return date.fromisoformat(raw)


def resolve_report_params(*, weeks: int, from_date: str | None, to_date: str | None, agente_id: int | None) -> ReportParams:
    if to_date:
        fecha_hasta = _parse_date(to_date)
    else:
        fecha_hasta = date.today()

    if from_date:
        fecha_desde = _parse_date(from_date)
    else:
        fecha_desde = fecha_hasta - timedelta(weeks=max(1, int(weeks)))

    if fecha_desde > fecha_hasta:
        raise ValueError("fecha_desde no puede ser mayor que fecha_hasta")

    return ReportParams(
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        agente_id=int(agente_id) if agente_id is not None else None,
    )


def _serialize_value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _write_csv(rows: list[dict[str, Any]], csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        csv_path.write_text("", encoding="utf-8")
        return

    fields = list(rows[0].keys())
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _serialize_value(v) for k, v in row.items()})


def _write_json(payload: dict[str, Any], json_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _fetch_rows(conn, query: str, params: ReportParams) -> list[dict[str, Any]]:
    result = conn.execute(
        text(query),
        {
            "fecha_desde": params.fecha_desde,
            "fecha_hasta": params.fecha_hasta,
            "agente_id": params.agente_id,
        },
    )
    return [dict(row._mapping) for row in result.fetchall()]


def run_report(params: ReportParams, out_dir: Path, output_format: str = "both") -> dict[str, Path]:
    engine = create_engine(config.DATABASE_URL, pool_pre_ping=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    detail_csv = out_dir / f"conciliacion_detalle_{timestamp}.csv"
    summary_csv = out_dir / f"conciliacion_resumen_{timestamp}.csv"
    json_path = out_dir / f"conciliacion_{timestamp}.json"

    with engine.connect() as conn:
        conn.execute(text("USE `database_manager`"))
        detail_rows = _fetch_rows(conn, DETAIL_QUERY, params)
        summary_rows = _fetch_rows(conn, SUMMARY_QUERY, params)

    generated: dict[str, Path] = {}
    if output_format in {"csv", "both"}:
        _write_csv(detail_rows, detail_csv)
        _write_csv(summary_rows, summary_csv)
        generated["detail_csv"] = detail_csv
        generated["summary_csv"] = summary_csv

    if output_format in {"json", "both"}:
        payload = {
            "generated_at": datetime.now().isoformat(),
            "filters": {
                "fecha_desde": params.fecha_desde.isoformat(),
                "fecha_hasta": params.fecha_hasta.isoformat(),
                "agente_id": params.agente_id,
            },
            "detail": [{k: _serialize_value(v) for k, v in row.items()} for row in detail_rows],
            "summary": [{k: _serialize_value(v) for k, v in row.items()} for row in summary_rows],
        }
        _write_json(payload, json_path)
        generated["json"] = json_path

    return generated


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generar reporte automatico de conciliacion semanal")
    parser.add_argument("--weeks", type=int, default=12, help="Semanas hacia atras si no se define --from-date")
    parser.add_argument("--from-date", type=str, default=None, help="Fecha inicio YYYY-MM-DD")
    parser.add_argument("--to-date", type=str, default=None, help="Fecha fin YYYY-MM-DD")
    parser.add_argument("--agent-id", type=int, default=None, help="Filtrar por agente")
    parser.add_argument(
        "--output-format",
        choices=["csv", "json", "both"],
        default="both",
        help="Formato de salida",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default=str(REPORT_DIR),
        help="Directorio de salida",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    try:
        params = resolve_report_params(
            weeks=args.weeks,
            from_date=args.from_date,
            to_date=args.to_date,
            agente_id=args.agent_id,
        )
    except ValueError as exc:
        print(f"Error de parametros: {exc}")
        return 2

    try:
        generated = run_report(params, Path(args.out_dir), output_format=args.output_format)
    except Exception as exc:
        print(f"Error generando reporte: {exc}")
        return 1

    for key, path in generated.items():
        print(f"{key}: {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
