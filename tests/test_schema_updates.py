"""Regresiones de actualizacion de esquema en init_db."""

from __future__ import annotations

from app.database import orm


def test_vw_agentes_qr_estado_tolera_columnas_opcionales_faltantes():
    """La vista no debe romper si telefono/uuid/qr_filename fueron eliminadas."""
    sql = orm._build_vw_agentes_qr_estado_sql({"id", "nombre", "es_activo", "fecha_creacion"})

    assert "NULL AS uuid" in sql
    assert "NULL AS telefono" in sql
    assert "0 AS tiene_qr" in sql
    assert "d.`id` AS id" in sql


def test_vw_operacion_actual_omite_join_estatus_si_no_existe_columna():
    """No debe referenciar cat_estatus_agente si estatus_codigo fue removida."""
    sql = orm._build_vw_agentes_operacion_actual_sql({"id", "nombre", "es_activo"})

    assert "LEFT JOIN cat_estatus_agente" not in sql
    assert "NULL AS estatus_codigo" in sql
    assert "NULL AS estatus_nombre" in sql
    assert "1 AS estatus_operativo" in sql


def test_vw_operacion_actual_tolera_datos_adicionales_faltante():
    """Cuando no existe datos_adicionales, los campos derivados deben salir en NULL."""
    sql = orm._build_vw_agentes_operacion_actual_sql({"id", "nombre", "es_activo", "estatus_codigo"})

    assert "NULL AS alias" in sql
    assert "NULL AS ubicacion" in sql
    assert "NULL AS grupo" in sql
    assert "NULL AS numero_voip" in sql


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeConn:
    def execute(self, statement, params=None):
        sql = str(statement)
        if "FROM information_schema.columns" in sql:
            table = (params or {}).get("table_name")
            if table == "agentes_operativos":
                return _Rows([
                    ("id",),
                    ("uuid",),
                    ("nombre",),
                    ("es_activo",),
                    ("qr_filename",),
                ])
            return _Rows([])
        return _Rows([])


def test_useful_views_map_includes_dynamic_payment_view():
    views = orm.get_useful_views_sql_map(_FakeConn())

    assert "vw_pagos_pendientes" in views
    assert "FROM pagos_semanales p" in views["vw_pagos_pendientes"]
    assert "LEFT JOIN agentes_operativos d" in views["vw_pagos_pendientes"]
