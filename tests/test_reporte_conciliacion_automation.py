from datetime import date
from pathlib import Path

import pytest

from scripts.generar_reporte_conciliacion import (
    ReportParams,
    _write_csv,
    _write_json,
    resolve_report_params,
)


def test_resolve_report_params_uses_weeks_when_dates_missing():
    params = resolve_report_params(weeks=4, from_date=None, to_date="2026-03-25", agente_id=None)
    assert params.fecha_hasta == date(2026, 3, 25)
    assert params.fecha_desde == date(2026, 2, 25)
    assert params.agente_id is None


def test_resolve_report_params_rejects_inverted_range():
    with pytest.raises(ValueError):
        resolve_report_params(
            weeks=1,
            from_date="2026-03-26",
            to_date="2026-03-25",
            agente_id=None,
        )


def test_write_csv_writes_header_and_rows(tmp_path: Path):
    rows = [
        {"agente_id": 1, "estatus": "OK", "monto": 50.0},
        {"agente_id": 2, "estatus": "REVISAR_MOVIMIENTOS", "monto": 75.5},
    ]
    csv_path = tmp_path / "salida.csv"

    _write_csv(rows, csv_path)

    text = csv_path.read_text(encoding="utf-8")
    assert "agente_id,estatus,monto" in text
    assert "1,OK,50.0" in text


def test_write_json_persists_payload(tmp_path: Path):
    payload = {
        "filters": {
            "fecha_desde": "2026-03-01",
            "fecha_hasta": "2026-03-25",
            "agente_id": None,
        },
        "summary": [{"semana_inicio": "2026-03-24", "agentes_ok": 10}],
    }
    json_path = tmp_path / "salida.json"

    _write_json(payload, json_path)

    stored = json_path.read_text(encoding="utf-8")
    assert "agentes_ok" in stored
    assert "2026-03-01" in stored


def test_report_params_dataclass_shape():
    params = ReportParams(
        fecha_desde=date(2026, 3, 1),
        fecha_hasta=date(2026, 3, 25),
        agente_id=99,
    )
    assert params.agente_id == 99
