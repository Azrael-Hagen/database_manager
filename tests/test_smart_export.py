"""
Tests for /api/smart-export endpoints and export_formats utilities.

Coverage:
- write_txt / write_dat output correctness
- list_export_tables: public tables vs. admin-only tables
- list_table_fields: column introspection
- smart_export POST: field selection, filters (all operators), formats
- Security: viewer blocked from admin-only tables; unauthenticated blocked
"""

from __future__ import annotations

import io
import json
import uuid
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.database.orm import get_db
from app.database.repositorios import RepositorioUsuario
from app.models import DatoImportado
from app.schemas import UsuarioCrear
from app.security import create_access_token
from app.utils.export_formats import write_dat, write_txt
from main import app
from tests.smart_test_db import TestingSessionLocal, override_get_db

# NOTE: test_smart_import.py registers the same override; both share the same
# in-memory database via smart_test_db.py – no cross-file state leak.
app.dependency_overrides[get_db] = override_get_db

client = TestClient(app, base_url="https://testserver:8443")


@pytest.fixture(autouse=True)
def _bind_smart_export_db_override():
    # test_sin_linea_e2e and other modules mutate dependency_overrides globally.
    # Rebind here to keep this suite isolated.
    app.dependency_overrides[get_db] = override_get_db
    yield


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------


def _make_token(rol: str = "capture") -> str:
    suf = uuid.uuid4().hex[:6]
    db = TestingSessionLocal()
    repo = RepositorioUsuario(db)
    username = f"{rol}_{suf}"
    if not repo.obtener_por_username(username):
        repo.crear(
            UsuarioCrear(
                username=username,
                email=f"{username}@test.com",
                password="Test1234!",
                nombre_completo="Export Test",
                rol=rol,
                es_admin=(rol in {"admin", "super_admin"}),
            )
        )
    db.close()
    return create_access_token({"sub": username, "rol": rol})


def _auth(rol: str = "capture") -> dict:
    return {"Authorization": f"Bearer {_make_token(rol)}"}


# ---------------------------------------------------------------------------
# Unit tests: export_formats
# ---------------------------------------------------------------------------


class TestExportFormats:
    def test_write_txt_header_and_rows(self):
        data = [{"a": "1", "b": "2"}, {"a": "3", "b": None}]
        result = write_txt(data, ["a", "b"])
        lines = result.decode("utf-8-sig").splitlines()
        assert lines[0] == "a\tb"
        assert lines[1] == "1\t2"
        assert lines[2] == "3\t"  # None serialized as empty string

    def test_write_txt_custom_delimiter(self):
        data = [{"x": "hello", "y": "world"}]
        result = write_txt(data, ["x", "y"], delimiter=",")
        lines = result.decode("utf-8-sig").splitlines()
        assert lines[0] == "x,y"
        assert lines[1] == "hello,world"

    def test_write_dat_pipe_delimiter(self):
        data = [{"col1": "val1", "col2": "val2"}]
        result = write_dat(data, ["col1", "col2"])
        lines = result.decode("utf-8-sig").splitlines()
        assert lines[0] == "col1|col2"
        assert lines[1] == "val1|val2"

    def test_write_dat_escapes_embedded_delimiter(self):
        data = [{"note": "a|b|c"}]  # value contains the pipe delimiter
        result = write_dat(data, ["note"])
        lines = result.decode("utf-8-sig").splitlines()
        header, data_line = lines[0], lines[1]
        assert header == "note"
        # The embedded pipes should be escaped
        assert "\\|" in data_line or data_line == "a\\|b\\|c"

    def test_write_dat_escapes_newlines(self):
        data = [{"msg": "line1\nline2"}]
        result = write_dat(data, ["msg"])
        text = result.decode("utf-8-sig")
        # Should not contain a literal newline mid-field
        lines = text.splitlines()
        # Header + 1 data line only
        assert len(lines) == 2
        assert "\\n" in lines[1]

    def test_write_txt_boolean_serialization(self):
        data = [{"flag": True}, {"flag": False}]
        result = write_txt(data, ["flag"])
        lines = result.decode("utf-8-sig").splitlines()
        assert lines[1] == "1"
        assert lines[2] == "0"


# ---------------------------------------------------------------------------
# HTTP endpoint tests: list_export_tables
# ---------------------------------------------------------------------------


class TestListExportTables:
    def test_any_user_sees_public_tables(self):
        response = client.get("/api/smart-export/tables", headers=_auth("capture"))
        assert response.status_code == 200
        body = response.json()
        assert "agentes_operativos" in body["tablas"]
        assert "lineas_telefonicas" in body["tablas"]

    def test_admin_sees_extra_tables(self):
        response = client.get("/api/smart-export/tables", headers=_auth("admin"))
        assert response.status_code == 200
        body = response.json()
        assert "usuarios" in body["tablas"]
        assert "auditoria_acciones" in body["tablas"]

    def test_non_admin_does_not_see_admin_tables(self):
        response = client.get("/api/smart-export/tables", headers=_auth("capture"))
        assert response.status_code == 200
        body = response.json()
        assert "usuarios" not in body["tablas"]

    def test_unauthenticated_blocked(self):
        response = client.get("/api/smart-export/tables")
        # FastAPI OAuth2PasswordBearer returns 403 when no Authorization header is present
        assert response.status_code in {401, 403}


# ---------------------------------------------------------------------------
# HTTP endpoint tests: list_table_fields
# ---------------------------------------------------------------------------


class TestListTableFields:
    def test_fields_for_datos_importados(self):
        response = client.get(
            "/api/smart-export/fields/agentes_operativos",
            headers=_auth("capture"),
        )
        assert response.status_code == 200
        body = response.json()
        field_names = [c["campo"] for c in body["campos"]]
        assert "nombre" in field_names
        assert "email" in field_names
        assert "telefono" in field_names

    def test_disallowed_table_rejected(self):
        response = client.get(
            "/api/smart-export/fields/mysql",
            headers=_auth("capture"),
        )
        assert response.status_code == 400

    def test_admin_only_table_blocked_for_capture(self):
        response = client.get(
            "/api/smart-export/fields/usuarios",
            headers=_auth("capture"),
        )
        assert response.status_code == 403

    def test_admin_can_access_admin_table(self):
        response = client.get(
            "/api/smart-export/fields/usuarios",
            headers=_auth("admin"),
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# HTTP endpoint tests: smart_export POST
# ---------------------------------------------------------------------------


class TestSmartExport:
    @pytest.fixture(autouse=True)
    def _seed(self):
        """Seed two agents for filtering tests."""
        db = TestingSessionLocal()
        db.add(
            DatoImportado(
                uuid=str(uuid.uuid4()),
                nombre="Alpha Export",
                email=f"alpha_{uuid.uuid4().hex[:6]}@export.com",
                ciudad="Guadalajara",
                es_activo=True,
            )
        )
        db.add(
            DatoImportado(
                uuid=str(uuid.uuid4()),
                nombre="Beta Export",
                email=f"beta_{uuid.uuid4().hex[:6]}@export.com",
                ciudad="CDMX",
                es_activo=True,
            )
        )
        db.commit()
        db.close()

    def _export(self, payload: dict, rol: str = "capture") -> "Response":
        return client.post(
            "/api/smart-export/export",
            json=payload,
            headers=_auth(rol),
        )

    # ---- basic field selection ----

    def test_csv_export_returns_bytes(self):
        resp = self._export(
            {
                "tabla": "agentes_operativos",
                "campos": ["nombre", "email"],
                "formato": "csv",
            }
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        text = resp.content.decode("utf-8-sig")
        assert "nombre" in text
        assert "email" in text

    def test_excel_export_returns_xlsx(self):
        resp = self._export(
            {
                "tabla": "agentes_operativos",
                "campos": ["nombre", "email"],
                "formato": "excel",
            }
        )
        assert resp.status_code == 200
        assert "spreadsheetml" in resp.headers["content-type"]

    def test_txt_export_tab_delimited(self):
        resp = self._export(
            {
                "tabla": "agentes_operativos",
                "campos": ["nombre", "ciudad"],
                "formato": "txt",
            }
        )
        assert resp.status_code == 200
        text = resp.content.decode("utf-8-sig")
        header_line = text.splitlines()[0]
        assert "\t" in header_line

    def test_dat_export_pipe_delimited(self):
        resp = self._export(
            {
                "tabla": "agentes_operativos",
                "campos": ["nombre", "ciudad"],
                "formato": "dat",
            }
        )
        assert resp.status_code == 200
        text = resp.content.decode("utf-8-sig")
        header_line = text.splitlines()[0]
        assert "|" in header_line

    # ---- filters ----

    def test_filter_eq(self):
        resp = self._export(
            {
                "tabla": "agentes_operativos",
                "campos": ["nombre", "ciudad"],
                "filtros": [{"campo": "ciudad", "operador": "eq", "valor": "Guadalajara"}],
                "formato": "csv",
            }
        )
        assert resp.status_code == 200
        text = resp.content.decode("utf-8-sig")
        # All returned rows should be from Guadalajara
        data_lines = text.strip().splitlines()[1:]  # skip header
        for line in data_lines:
            assert "Guadalajara" in line

    def test_filter_contains(self):
        resp = self._export(
            {
                "tabla": "agentes_operativos",
                "campos": ["nombre"],
                "filtros": [{"campo": "nombre", "operador": "contains", "valor": "Export"}],
                "formato": "csv",
            }
        )
        assert resp.status_code == 200
        text = resp.content.decode("utf-8-sig")
        data_lines = text.strip().splitlines()[1:]
        assert len(data_lines) >= 2  # seeded Alpha Export and Beta Export

    def test_filter_is_null(self):
        resp = self._export(
            {
                "tabla": "agentes_operativos",
                "campos": ["nombre", "empresa"],
                "filtros": [{"campo": "empresa", "operador": "is_null"}],
                "formato": "csv",
            }
        )
        assert resp.status_code == 200

    def test_filter_in(self):
        resp = self._export(
            {
                "tabla": "agentes_operativos",
                "campos": ["ciudad"],
                "filtros": [
                    {
                        "campo": "ciudad",
                        "operador": "in",
                        "valor": "Guadalajara,CDMX",
                    }
                ],
                "formato": "csv",
            }
        )
        assert resp.status_code == 200
        text = resp.content.decode("utf-8-sig")
        data_lines = text.strip().splitlines()[1:]
        assert len(data_lines) >= 2

    # ---- validation ----

    def test_invalid_format_rejected(self):
        resp = self._export(
            {"tabla": "agentes_operativos", "campos": ["nombre"], "formato": "pdf"}
        )
        assert resp.status_code == 422

    def test_disallowed_table_rejected(self):
        resp = self._export(
            {"tabla": "information_schema", "campos": ["nombre"], "formato": "csv"}
        )
        assert resp.status_code == 422  # Pydantic validator rejects before handler

    def test_admin_table_blocked_for_capture(self):
        resp = self._export(
            {"tabla": "usuarios", "campos": ["username"], "formato": "csv"},
            rol="capture",
        )
        assert resp.status_code == 403

    def test_admin_table_accessible_for_admin(self):
        resp = self._export(
            {"tabla": "usuarios", "campos": ["username", "email"], "formato": "csv"},
            rol="admin",
        )
        assert resp.status_code == 200

    def test_invalid_column_rejected(self):
        resp = self._export(
            {
                "tabla": "agentes_operativos",
                "campos": ["nombre", "nonexistent_col_xyz"],
                "formato": "csv",
            }
        )
        assert resp.status_code == 400

    def test_invalid_filter_operator_rejected(self):
        resp = self._export(
            {
                "tabla": "agentes_operativos",
                "campos": ["nombre"],
                "filtros": [{"campo": "nombre", "operador": "DROP TABLE", "valor": "x"}],
                "formato": "csv",
            }
        )
        assert resp.status_code == 422

    def test_empty_campos_rejected(self):
        resp = self._export(
            {"tabla": "agentes_operativos", "campos": [], "formato": "csv"}
        )
        assert resp.status_code == 422

    def test_limit_respected(self):
        resp = self._export(
            {
                "tabla": "agentes_operativos",
                "campos": ["nombre"],
                "formato": "csv",
                "limite": 1,
            }
        )
        assert resp.status_code == 200
        text = resp.content.decode("utf-8-sig")
        data_lines = [l for l in text.strip().splitlines() if l][1:]  # skip header
        assert len(data_lines) == 1

    def test_custom_filename_in_header(self):
        resp = self._export(
            {
                "tabla": "agentes_operativos",
                "campos": ["nombre"],
                "formato": "csv",
                "nombre_archivo": "mi_reporte",
            }
        )
        assert resp.status_code == 200
        cd = resp.headers.get("content-disposition", "")
        assert "mi_reporte.csv" in cd

    def test_unauthenticated_blocked(self):
        resp = client.post(
            "/api/smart-export/export",
            json={"tabla": "agentes_operativos", "campos": ["nombre"], "formato": "csv"},
        )
        # FastAPI OAuth2PasswordBearer returns 403 when no Authorization header is present
        assert resp.status_code in {401, 403}
