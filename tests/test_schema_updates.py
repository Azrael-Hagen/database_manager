"""Regresiones de actualizacion de esquema en init_db."""

from __future__ import annotations

from app.database import orm


class _FakeConnection:
    def __init__(self):
        self.executed_sql: list[str] = []

    def execute(self, statement, params=None):
        self.executed_sql.append(str(statement))
        return None


class _FakeBeginContext:
    def __init__(self, connection: _FakeConnection):
        self._connection = connection

    def __enter__(self):
        return self._connection

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeEngine:
    def __init__(self, connection: _FakeConnection):
        self._connection = connection

    def begin(self):
        return _FakeBeginContext(self._connection)


def test_schema_updates_adds_qr_columns_independent_of_pago_index(monkeypatch):
    """Debe crear columnas QR aunque el indice de pagos ya exista."""
    fake_connection = _FakeConnection()
    fake_engine = _FakeEngine(fake_connection)

    monkeypatch.setattr(orm, "engine", fake_engine)

    def _fake_column_exists(connection, table_name: str, column_name: str) -> bool:
        if table_name == "datos_importados" and column_name in {"qr_impreso", "qr_impreso_at"}:
            return False
        return True

    def _fake_index_exists(connection, table_name: str, index_name: str) -> bool:
        if table_name == "datos_importados" and index_name == "ix_datos_importados_qr_impreso":
            return False
        if table_name == "pagos_semanales" and index_name == "ix_pagos_semanales_agente_semana_pagado":
            return True
        return True

    monkeypatch.setattr(orm, "_column_exists", _fake_column_exists)
    monkeypatch.setattr(orm, "_index_exists", _fake_index_exists)
    monkeypatch.setattr(orm, "_execute_optional", lambda *args, **kwargs: None)

    orm._ensure_core_schema_updates()

    full_sql = "\n".join(fake_connection.executed_sql)
    assert "ADD COLUMN `qr_impreso`" in full_sql
    assert "ADD COLUMN `qr_impreso_at`" in full_sql
    assert "ix_datos_importados_qr_impreso" in full_sql
