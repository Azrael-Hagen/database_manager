from types import SimpleNamespace

from app.services.lineas import (
    build_empty_line_sync_result,
    normalize_categoria_linea,
    normalize_estado_conexion,
    parse_fecha_ultimo_uso,
    serialize_linea_operativa,
)
from app.services.qr_security import build_secure_qr_token, decode_secure_qr_token


def test_qr_secure_token_roundtrip():
    token = build_secure_qr_token(agente_id=7, linea_id=12, linea_numero="5551000")
    payload = decode_secure_qr_token(token)
    assert payload["agente_id"] == 7
    assert payload["linea_id"] == 12
    assert payload["linea_numero"] == "5551000"
    assert payload["nonce"]


def test_parse_fecha_ultimo_uso_admite_fecha_iso_simple():
    parsed = parse_fecha_ultimo_uso("2026-03-20")
    assert parsed.isoformat() == "2026-03-20T00:00:00"


def test_serialize_linea_operativa_normaliza_campos():
    linea = SimpleNamespace(
        id=3,
        numero="5551234567",
        tipo="MANUAL",
        descripcion="Alta manual",
        categoria_linea=None,
        estado_conexion=None,
        fecha_ultimo_uso=None,
    )
    agente = SimpleNamespace(id=9, nombre="Agente Demo", telefono="5550000")
    assignment = SimpleNamespace(agente=agente, fecha_asignacion=None)

    payload = serialize_linea_operativa(linea, assignment=assignment, known_codes=["555"])
    assert payload["categoria_linea"] == "NO_DEFINIDA"
    assert payload["estado_conexion"] == "DESCONOCIDA"
    assert payload["lada"] == "555"
    assert payload["agente"]["id"] == 9
    assert payload["ocupada"] is True


def test_line_helpers_defaults_estables():
    assert normalize_categoria_linea("") == "NO_DEFINIDA"
    assert normalize_estado_conexion(None) == "DESCONOCIDA"
    assert build_empty_line_sync_result()["source"] == 0
