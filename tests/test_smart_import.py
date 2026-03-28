"""
Tests for smart_importer module and /api/smart-import endpoints.

Coverage:
- suggest_mapping: exact, synonym, fuzzy, unknown
- analyze_file: CSV, Excel (mocked), empty
- agent_has_active_line / find_existing_agent using in-memory SQLite
- preview_import: new / update / no-change classification
- HTTP endpoints: analyze, preview, execute (insert / update / upsert)
- Security: viewer role is blocked from import endpoints
"""

from __future__ import annotations

import csv
import io
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.database.orm import get_db
from app.database.repositorios import RepositorioUsuario
from app.importers.smart_importer import (
    agent_has_active_line,
    analyze_file,
    find_existing_agent,
    preview_import,
    suggest_mapping,
)
from app.models import AgenteLineaAsignacion, DatoImportado, LineaTelefonica
from app.schemas import UsuarioCrear
from app.security import create_access_token
from main import app
from tests.smart_test_db import TestingSessionLocal, override_get_db

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app, base_url="https://testserver:8443")


@pytest.fixture(autouse=True)
def _bind_smart_import_db_override():
    # test_sin_linea_e2e and other modules mutate dependency_overrides globally.
    # Rebind here to keep this suite isolated.
    app.dependency_overrides[get_db] = override_get_db
    yield


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_capture_token(suffix: str = "") -> str:
    suf = suffix or uuid.uuid4().hex[:6]
    db = TestingSessionLocal()
    repo = RepositorioUsuario(db)
    username = f"cap_{suf}"
    if not repo.obtener_por_username(username):
        repo.crear(
            UsuarioCrear(
                username=username,
                email=f"{username}@test.com",
                password="Test1234!",
                nombre_completo="Capture User",
                rol="capture",
                es_admin=False,
            )
        )
    db.close()
    return create_access_token({"sub": username, "rol": "capture"})


def _make_viewer_token(suffix: str = "") -> str:
    suf = suffix or uuid.uuid4().hex[:6]
    db = TestingSessionLocal()
    repo = RepositorioUsuario(db)
    username = f"view_{suf}"
    if not repo.obtener_por_username(username):
        repo.crear(
            UsuarioCrear(
                username=username,
                email=f"{username}@test.com",
                password="Test1234!",
                nombre_completo="Viewer User",
                rol="viewer",
                es_admin=False,
            )
        )
    db.close()
    return create_access_token({"sub": username, "rol": "viewer"})


def _csv_bytes(rows: list[dict]) -> bytes:
    """Serialize a list of dicts to CSV bytes."""
    if not rows:
        return b""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


# ===========================================================================
# Unit tests: suggest_mapping
# ===========================================================================


class TestSuggestMapping:
    def test_exact_canonical_field(self):
        """'nombre' maps to itself with full confidence."""
        r = suggest_mapping("nombre")
        assert r["campo"] == "nombre"
        assert r["confianza"] == 1.0
        assert r["tipo"] == "exacta"

    def test_synonym_name_maps_to_nombre(self):
        """'name' is a known synonym for 'nombre'."""
        r = suggest_mapping("name")
        assert r["campo"] == "nombre"
        assert r["confianza"] == 1.0
        assert r["tipo"] == "sinonimo"

    def test_synonym_correo_maps_to_email(self):
        r = suggest_mapping("correo")
        assert r["campo"] == "email"

    def test_fuzzy_typo(self):
        """A close misspelling should still resolve via fuzzy matching."""
        r = suggest_mapping("nombr")   # one char short
        assert r["campo"] == "nombre"
        assert r["tipo"] == "fuzzy"
        assert r["confianza"] >= 0.75

    def test_unknown_header(self):
        """A totally unrelated header should return campo=None."""
        r = suggest_mapping("zzzunrelatedxxx123")
        assert r["campo"] is None
        assert r["tipo"] == "desconocido"
        assert r["confianza"] == 0.0

    def test_header_case_insensitive(self):
        """Matching should be case-insensitive."""
        r = suggest_mapping("NOMBRE")
        assert r["campo"] == "nombre"

    def test_header_with_spaces(self):
        """Spaces should be normalized to underscores before matching."""
        r = suggest_mapping("full name")
        assert r["campo"] == "nombre"

    def test_telefono_synonyms(self):
        for header in ["celular", "mobile", "phone"]:
            r = suggest_mapping(header)
            assert r["campo"] == "telefono", f"Expected 'telefono' for '{header}'"


# ===========================================================================
# Unit tests: analyze_file
# ===========================================================================


class TestAnalyzeFile:
    def test_csv_detects_columns(self):
        rows = [
            {"nombre": "Ana", "email": "ana@x.com", "telefono": "555"},
            {"nombre": "Bob", "email": "bob@x.com", "telefono": "556"},
        ]
        content = _csv_bytes(rows)
        result = analyze_file(content, "test.csv")

        assert result["total_filas"] == 2
        assert len(result["columnas_detectadas"]) == 3
        assert result["errores"] == []

        campos = {c["header"]: c["campo"] for c in result["columnas_detectadas"]}
        assert campos["nombre"] == "nombre"
        assert campos["email"] == "email"
        assert campos["telefono"] == "telefono"

    def test_csv_sample_limited_to_five(self):
        rows = [{"nombre": f"User{i}"} for i in range(10)]
        content = _csv_bytes(rows)
        result = analyze_file(content, "big.csv")
        assert len(result["muestra"]) == 5

    def test_empty_csv_returns_error(self):
        content = b"nombre,email\n"  # header only, no data rows
        result = analyze_file(content, "empty.csv")
        assert result["total_filas"] == 0
        assert result["errores"]

    def test_semicolon_delimiter(self):
        content = b"nombre;correo\nAna;ana@x.com"
        result = analyze_file(content, "semi.csv", delimiter=";")
        assert result["total_filas"] == 1
        campos = {c["header"]: c["campo"] for c in result["columnas_detectadas"]}
        assert campos["correo"] == "email"

    def test_unknown_columns_flagged(self):
        content = b"foo,bar,baz\n1,2,3"
        result = analyze_file(content, "unknown.csv")
        unknown = [
            c for c in result["columnas_detectadas"] if c["tipo"] == "desconocido"
        ]
        # All three headers are unrecognized
        assert len(unknown) == 3


# ===========================================================================
# Unit tests: agent_has_active_line, find_existing_agent
# ===========================================================================


class TestAgentHelpers:
    @pytest.fixture(autouse=True)
    def _db(self):
        self.db = TestingSessionLocal()
        yield
        self.db.rollback()
        self.db.close()

    def _create_agent(self, email: str = None, telefono: str = None) -> DatoImportado:
        agent = DatoImportado(
            uuid=str(uuid.uuid4()),
            nombre="Test Agent",
            email=email or f"{uuid.uuid4().hex}@test.com",
            telefono=telefono,
            es_activo=True,
        )
        self.db.add(agent)
        self.db.commit()
        self.db.refresh(agent)
        return agent

    def _create_line(self) -> LineaTelefonica:
        linea = LineaTelefonica(numero=f"5550{uuid.uuid4().int % 10000:04d}", es_activa=True)
        self.db.add(linea)
        self.db.commit()
        self.db.refresh(linea)
        return linea

    def test_agent_has_no_line(self):
        agent = self._create_agent()
        assert agent_has_active_line(agent.id, self.db) is False

    def test_agent_has_active_line(self):
        agent = self._create_agent()
        linea = self._create_line()
        asignacion = AgenteLineaAsignacion(
            agente_id=agent.id,
            linea_id=linea.id,
            es_activa=True,
        )
        self.db.add(asignacion)
        self.db.commit()
        assert agent_has_active_line(agent.id, self.db) is True

    def test_inactive_assignment_not_counted(self):
        agent = self._create_agent()
        linea = self._create_line()
        asignacion = AgenteLineaAsignacion(
            agente_id=agent.id,
            linea_id=linea.id,
            es_activa=False,  # inactive
        )
        self.db.add(asignacion)
        self.db.commit()
        assert agent_has_active_line(agent.id, self.db) is False

    def test_find_existing_agent_by_email(self):
        agent = self._create_agent(email="find@example.com")
        found = find_existing_agent({"email": "find@example.com"}, self.db)
        assert found is not None
        assert found.id == agent.id

    def test_find_existing_agent_not_found(self):
        result = find_existing_agent({"email": "nobody@nope.com"}, self.db)
        assert result is None


# ===========================================================================
# Unit tests: preview_import
# ===========================================================================


class TestPreviewImport:
    @pytest.fixture(autouse=True)
    def _db(self):
        self.db = TestingSessionLocal()
        yield
        self.db.rollback()
        self.db.close()

    def test_all_new_records(self):
        content = _csv_bytes(
            [
                {"nombre": "Alpha", "email": "alpha@new.com"},
                {"nombre": "Beta", "email": "beta@new.com"},
            ]
        )
        mapping = {"nombre": "nombre", "email": "email"}
        result = preview_import(content, "test.csv", mapping, db=self.db)
        assert result["nuevos"] == 2
        assert result["actualizaciones"] == 0
        assert result["sin_cambios"] == 0

    def test_detects_update_on_existing_email(self):
        # Create an existing agent
        existing = DatoImportado(
            uuid=str(uuid.uuid4()),
            nombre="Old Name",
            email="existing@test.com",
            es_activo=True,
        )
        self.db.add(existing)
        self.db.commit()

        # CSV with same email but different nombre
        content = _csv_bytes(
            [{"nombre": "New Name", "email": "existing@test.com"}]
        )
        mapping = {"nombre": "nombre", "email": "email"}
        result = preview_import(content, "test.csv", mapping, db=self.db)
        assert result["actualizaciones"] == 1
        assert result["nuevos"] == 0

    def test_detects_no_change(self):
        existing = DatoImportado(
            uuid=str(uuid.uuid4()),
            nombre="Same Name",
            email="same@test.com",
            datos_adicionales=json.dumps({"alias": "Same Name"}, ensure_ascii=False),
            es_activo=True,
        )
        self.db.add(existing)
        self.db.commit()

        content = _csv_bytes([{"nombre": "Same Name", "email": "same@test.com"}])
        mapping = {"nombre": "nombre", "email": "email"}
        result = preview_import(content, "test.csv", mapping, db=self.db)
        assert result["sin_cambios"] == 1
        assert result["nuevos"] == 0
        assert result["actualizaciones"] == 0

    def test_mixed_actions(self):
        existing = DatoImportado(
            uuid=str(uuid.uuid4()),
            nombre="Old",
            email="old@test.com",
            es_activo=True,
        )
        self.db.add(existing)
        self.db.commit()

        content = _csv_bytes(
            [
                {"nombre": "New", "email": "brand_new@test.com"},   # new
                {"nombre": "Updated", "email": "old@test.com"},      # update
            ]
        )
        mapping = {"nombre": "nombre", "email": "email"}
        result = preview_import(content, "test.csv", mapping, db=self.db)
        assert result["nuevos"] == 1
        assert result["actualizaciones"] == 1


# ===========================================================================
# HTTP endpoint tests
# ===========================================================================


class TestSmartImportEndpoints:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.token = _make_capture_token()
        self.headers = {"Authorization": f"Bearer {self.token}"}

    # ---- analyze ----

    def test_analyze_returns_columns(self):
        content = _csv_bytes([{"nombre": "Ana", "correo": "ana@x.com"}])
        response = client.post(
            "/api/smart-import/analyze",
            files={"archivo": ("data.csv", content, "text/csv")},
            data={"delimitador": ","},
            headers=self.headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["datos"]["total_filas"] == 1
        campos = {
            c["header"]: c["campo"]
            for c in body["datos"]["columnas_detectadas"]
        }
        assert campos["correo"] == "email"

    def test_analyze_rejects_unsupported_extension(self):
        response = client.post(
            "/api/smart-import/analyze",
            files={"archivo": ("data.pdf", b"%PDF", "application/pdf")},
            data={"delimitador": ","},
            headers=self.headers,
        )
        assert response.status_code == 400

    def test_analyze_requires_at_least_capture_role(self):
        viewer_headers = {"Authorization": f"Bearer {_make_viewer_token()}"}
        content = _csv_bytes([{"nombre": "X"}])
        response = client.post(
            "/api/smart-import/analyze",
            files={"archivo": ("d.csv", content, "text/csv")},
            data={"delimitador": ","},
            headers=viewer_headers,
        )
        assert response.status_code == 403

    # ---- preview ----

    def test_preview_classifies_new_records(self):
        content = _csv_bytes([{"nombre": "NuevoX", "email": f"{uuid.uuid4().hex}@x.com"}])
        mapping = json.dumps({"nombre": "nombre", "email": "email"})
        response = client.post(
            "/api/smart-import/preview",
            files={"archivo": ("d.csv", content, "text/csv")},
            data={"delimitador": ",", "mapeo": mapping},
            headers=self.headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["datos"]["nuevos"] >= 1

    def test_preview_includes_ai_diagnostics(self):
        content = _csv_bytes([
            {
                "nombre": "Demo User",
                "email": "demo@example.com",
                "telefono": "11111111",
                "ubicacion": "Centro",
            }
        ])
        mapping = json.dumps(
            {
                "nombre": "nombre",
                "email": "email",
                "telefono": "telefono",
                "ubicacion": "ubicacion",
            }
        )
        response = client.post(
            "/api/smart-import/preview",
            files={"archivo": ("d.csv", content, "text/csv")},
            data={"delimitador": ",", "mapeo": mapping},
            headers=self.headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert "diagnostico_ai" in body["datos"]
        assert body["datos"]["diagnostico_ai"]["alertas_test_data"]
        assert "riesgos_priorizados" in body["datos"]["diagnostico_ai"]

    def test_preview_invalid_json_mapeo(self):
        content = _csv_bytes([{"nombre": "X"}])
        response = client.post(
            "/api/smart-import/preview",
            files={"archivo": ("d.csv", content, "text/csv")},
            data={"delimitador": ",", "mapeo": "not_json{{"},
            headers=self.headers,
        )
        assert response.status_code == 400

    # ---- execute ----

    def test_execute_insert_creates_agent(self):
        unique_email = f"{uuid.uuid4().hex}@exec.com"
        content = _csv_bytes(
            [{"nombre": "ExecAgent", "email": unique_email, "telefono": "5550001"}]
        )
        mapping = json.dumps(
            {"nombre": "nombre", "email": "email", "telefono": "telefono"}
        )
        response = client.post(
            "/api/smart-import/execute",
            files={"archivo": ("d.csv", content, "text/csv")},
            data={"delimitador": ",", "mapeo": mapping, "modo": "insertar", "confirmacion": "true"},
            headers=self.headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["datos"]["insertados"] == 1
        assert body["datos"]["errores"] == []

        # Verify in DB
        db = TestingSessionLocal()
        agent = db.query(DatoImportado).filter_by(email=unique_email).first()
        db.close()
        assert agent is not None
        assert agent.nombre == "ExecAgent"

    def test_execute_insert_skips_duplicates(self):
        # Create pre-existing agent
        unique_email = f"{uuid.uuid4().hex}@dup.com"
        db = TestingSessionLocal()
        db.add(
            DatoImportado(
                uuid=str(uuid.uuid4()),
                nombre="Existing",
                email=unique_email,
                es_activo=True,
            )
        )
        db.commit()
        db.close()

        # Try to insert the same email in "insertar" mode
        content = _csv_bytes([{"nombre": "Dupe", "email": unique_email}])
        mapping = json.dumps({"nombre": "nombre", "email": "email"})
        response = client.post(
            "/api/smart-import/execute",
            files={"archivo": ("d.csv", content, "text/csv")},
            data={"delimitador": ",", "mapeo": mapping, "modo": "insertar", "confirmacion": "true"},
            headers=self.headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["datos"]["insertados"] == 0
        assert body["datos"]["omitidos"] == 1

    def test_execute_update_mode(self):
        unique_email = f"{uuid.uuid4().hex}@upd.com"
        db = TestingSessionLocal()
        db.add(
            DatoImportado(
                uuid=str(uuid.uuid4()),
                nombre="Before",
                email=unique_email,
                es_activo=True,
            )
        )
        db.commit()
        db.close()

        content = _csv_bytes([{"nombre": "After", "email": unique_email}])
        mapping = json.dumps({"nombre": "nombre", "email": "email"})
        response = client.post(
            "/api/smart-import/execute",
            files={"archivo": ("d.csv", content, "text/csv")},
            data={"delimitador": ",", "mapeo": mapping, "modo": "actualizar", "confirmacion": "true"},
            headers=self.headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["datos"]["actualizados"] == 1

        db = TestingSessionLocal()
        agent = db.query(DatoImportado).filter_by(email=unique_email).first()
        db.close()
        assert agent.nombre == "After"

    def test_execute_invalid_mode_rejected(self):
        content = _csv_bytes([{"nombre": "X"}])
        mapping = json.dumps({"nombre": "nombre"})
        response = client.post(
            "/api/smart-import/execute",
            files={"archivo": ("d.csv", content, "text/csv")},
            data={"delimitador": ",", "mapeo": mapping, "modo": "INVALID", "confirmacion": "true"},
            headers=self.headers,
        )
        assert response.status_code == 400

    def test_execute_requires_confirmation(self):
        content = _csv_bytes([{"nombre": "NeedsConfirm", "email": f"{uuid.uuid4().hex}@x.com"}])
        mapping = json.dumps({"nombre": "nombre", "email": "email"})
        response = client.post(
            "/api/smart-import/execute",
            files={"archivo": ("d.csv", content, "text/csv")},
            data={"delimitador": ",", "mapeo": mapping, "modo": "insertar"},
            headers=self.headers,
        )
        assert response.status_code == 400

    def test_execute_strict_mode_blocks_line_conflicts(self):
        db = TestingSessionLocal()
        occupant = DatoImportado(
            uuid=str(uuid.uuid4()),
            nombre="Occupant",
            email=f"{uuid.uuid4().hex}@occ.com",
            es_activo=True,
        )
        db.add(occupant)
        db.flush()

        line = LineaTelefonica(numero="VOIP-9001", es_activa=True)
        db.add(line)
        db.flush()

        db.add(
            AgenteLineaAsignacion(
                agente_id=occupant.id,
                linea_id=line.id,
                es_activa=True,
            )
        )
        db.commit()
        db.close()

        content = _csv_bytes(
            [{"nombre": "Nuevo", "email": f"{uuid.uuid4().hex}@x.com", "numero_voip": "VOIP-9001"}]
        )
        mapping = json.dumps({"nombre": "nombre", "email": "email", "numero_voip": "numero_voip"})
        response = client.post(
            "/api/smart-import/execute",
            files={"archivo": ("d.csv", content, "text/csv")},
            data={
                "delimitador": ",",
                "mapeo": mapping,
                "modo": "insertar_o_actualizar",
                "confirmacion": "true",
                "modo_estricto_conflictos": "true",
            },
            headers=self.headers,
        )
        assert response.status_code == 409

    def test_execute_upsert_mode(self):
        unique_email = f"{uuid.uuid4().hex}@ups.com"
        db = TestingSessionLocal()
        db.add(
            DatoImportado(
                uuid=str(uuid.uuid4()),
                nombre="OldName",
                email=unique_email,
                es_activo=True,
            )
        )
        db.commit()
        db.close()

        brand_new = f"{uuid.uuid4().hex}@ups.com"
        content = _csv_bytes(
            [
                {"nombre": "NewName", "email": unique_email},  # update
                {"nombre": "BrandNew", "email": brand_new},    # insert
            ]
        )
        mapping = json.dumps({"nombre": "nombre", "email": "email"})
        response = client.post(
            "/api/smart-import/execute",
            files={"archivo": ("d.csv", content, "text/csv")},
            data={"delimitador": ",", "mapeo": mapping, "modo": "insertar_o_actualizar", "confirmacion": "true"},
            headers=self.headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["datos"]["actualizados"] == 1
        assert body["datos"]["insertados"] == 1

    def test_execute_requires_capture_role(self):
        viewer_headers = {"Authorization": f"Bearer {_make_viewer_token()}"}
        content = _csv_bytes([{"nombre": "X"}])
        mapping = json.dumps({"nombre": "nombre"})
        response = client.post(
            "/api/smart-import/execute",
            files={"archivo": ("d.csv", content, "text/csv")},
            data={"delimitador": ",", "mapeo": mapping, "modo": "insertar", "confirmacion": "true"},
            headers=viewer_headers,
        )
        assert response.status_code == 403
