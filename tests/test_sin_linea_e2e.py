"""E2E de la funcionalidad Sin Linea."""

import os
import uuid
from datetime import timedelta
from urllib.parse import urlparse

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models as _all_models  # noqa: F401
from app.database.orm import Base, get_db
from app.models import AgenteLineaAsignacion, DatoImportado, LineaTelefonica
from app.security import create_access_token
from app.utils.startup_tasks import auto_qr_al_inicio, reporte_sin_linea_inicio
from main import app


# SQLite en memoria compartida por todas las sesiones del test.
_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
Base.metadata.create_all(bind=_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app, raise_server_exceptions=False, base_url="https://testserver:8443")

_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
_INDEX_HTML = os.path.join(_REPO_ROOT, "web", "index.html")
_MAIN_JS = os.path.join(_REPO_ROOT, "web", "js", "main.js")
_STYLE_CSS = os.path.join(_REPO_ROOT, "web", "css", "style.css")


def _db() -> Session:
    return TestingSessionLocal()


def _clear_agent_tables() -> None:
    db = _db()
    try:
        db.query(AgenteLineaAsignacion).delete()
        db.query(LineaTelefonica).delete()
        db.query(DatoImportado).delete()
        db.commit()
    finally:
        db.close()


def _mk_agente(nombre: str, *, activo: bool = True, con_qr: bool = False) -> DatoImportado:
    db = _db()
    try:
        ag = DatoImportado(
            nombre=nombre,
            email=f"{nombre.lower().replace(' ', '_')}@example.com",
            es_activo=activo,
            qr_filename="dummy.png" if con_qr else None,
        )
        db.add(ag)
        db.commit()
        db.refresh(ag)
        return ag
    finally:
        db.close()


def _asignar_linea(agente_id: int, *, activa: bool = True) -> None:
    db = _db()
    try:
        linea = LineaTelefonica(numero=f"555-{agente_id:06d}", es_activa=True)
        db.add(linea)
        db.flush()
        db.add(AgenteLineaAsignacion(agente_id=agente_id, linea_id=linea.id, es_activa=activa))
        db.commit()
    finally:
        db.close()


def _token(username: str, rol: str) -> str:
    unique = f"{username}_{uuid.uuid4().hex[:8]}"

    return create_access_token(
        data={
            "sub": unique,
            "id": 1,
            "es_admin": rol == "admin",
            "rol": rol,
            "email": f"{unique}@example.com",
        },
        expires_delta=timedelta(minutes=60),
    )


class TestStartupTasks:
    def setup_method(self):
        _clear_agent_tables()
        self.db = _db()

    def teardown_method(self):
        self.db.close()

    def test_auto_qr_sin_agentes(self):
        result = auto_qr_al_inicio(self.db)
        assert result.get("status") in ("ok", "skipped")
        assert result.get("totales_sin_qr", 0) == 0

    def test_auto_qr_procesa_agentes_sin_qr(self):
        self.db.add(DatoImportado(nombre="Startup A1", es_activo=True, qr_filename=None))
        self.db.add(DatoImportado(nombre="Startup A2", es_activo=True, qr_filename=None))
        self.db.commit()

        result = auto_qr_al_inicio(self.db)
        assert result["status"] == "ok"
        assert result["totales_sin_qr"] == 2
        assert result["generados"] + result["errores"] == 2

    def test_reporte_sin_linea_cuenta(self):
        self.db.add(DatoImportado(nombre="Sin linea", es_activo=True))
        self.db.commit()
        result = reporte_sin_linea_inicio(self.db)
        assert result["sin_linea"] >= 1

    def test_reporte_sin_linea_no_cuenta_con_linea_activa(self):
        ag = DatoImportado(nombre="Con linea", es_activo=True)
        self.db.add(ag)
        self.db.flush()
        linea = LineaTelefonica(numero="555-REPORTE")
        self.db.add(linea)
        self.db.flush()
        self.db.add(AgenteLineaAsignacion(agente_id=ag.id, linea_id=linea.id, es_activa=True))
        self.db.commit()

        result = reporte_sin_linea_inicio(self.db)
        assert result["sin_linea"] == 0


class TestEndpointSinLinea:
    @classmethod
    def setup_class(cls):
        cls.admin_headers = {"Authorization": f"Bearer {_token('e2e_admin_sinlinea', 'admin')}"}

    def setup_method(self):
        _clear_agent_tables()

    def test_requiere_auth(self):
        resp = client.get("/api/qr/agentes/sin-linea")
        assert resp.status_code in (401, 403)

    def test_lista_vacia(self):
        resp = client.get("/api/qr/agentes/sin-linea", headers=self.admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["total"] == 0
        assert body["data"] == []

    def test_incluye_solo_activos_sin_linea(self):
        _mk_agente("Sin Linea 1", activo=True, con_qr=False)
        con_linea = _mk_agente("Con Linea", activo=True, con_qr=False)
        _asignar_linea(con_linea.id, activa=True)
        _mk_agente("Inactivo", activo=False, con_qr=False)

        resp = client.get("/api/qr/agentes/sin-linea", headers=self.admin_headers)
        body = resp.json()
        names = [x["nombre"] for x in body["data"]]
        assert "Sin Linea 1" in names
        assert "Con Linea" not in names
        assert "Inactivo" not in names

    def test_linea_inactiva_cuenta_como_sin_linea(self):
        ag = _mk_agente("Linea Inactiva", activo=True, con_qr=False)
        _asignar_linea(ag.id, activa=False)
        resp = client.get("/api/qr/agentes/sin-linea", headers=self.admin_headers)
        names = [x["nombre"] for x in resp.json()["data"]]
        assert "Linea Inactiva" in names

    def test_busqueda_por_nombre(self):
        _mk_agente("Juan Buscar")
        _mk_agente("Maria Oculta")
        resp = client.get("/api/qr/agentes/sin-linea?search=Juan", headers=self.admin_headers)
        body = resp.json()
        names = [x["nombre"] for x in body["data"]]
        assert "Juan Buscar" in names
        assert "Maria Oculta" not in names

    def test_respuesta_tiene_campos_esperados(self):
        _mk_agente("Campos", con_qr=True)
        resp = client.get("/api/qr/agentes/sin-linea", headers=self.admin_headers)
        rec = resp.json()["data"][0]
        for field in ("id", "uuid", "nombre", "telefono", "tiene_qr", "qr_filename"):
            assert field in rec


class TestEndpointQrMasivo:
    @classmethod
    def setup_class(cls):
        cls.admin_headers = {"Authorization": f"Bearer {_token('e2e_admin_qr', 'admin')}"}
        cls.capture_headers = {"Authorization": f"Bearer {_token('e2e_capture_qr', 'capture')}"}
        cls.viewer_headers = {"Authorization": f"Bearer {_token('e2e_viewer_qr', 'viewer')}"}

    def setup_method(self):
        _clear_agent_tables()

    def test_requiere_auth(self):
        resp = client.post("/api/qr/agentes/generar-qr-masivo")
        assert resp.status_code in (401, 403)

    def test_viewer_no_puede(self):
        resp = client.post("/api/qr/agentes/generar-qr-masivo", headers=self.viewer_headers)
        assert resp.status_code == 403

    def test_capture_si_puede(self):
        resp = client.post("/api/qr/agentes/generar-qr-masivo", headers=self.capture_headers)
        assert resp.status_code == 200

    def test_procesa_pendientes(self):
        _mk_agente("Sin QR 1", con_qr=False)
        _mk_agente("Sin QR 2", con_qr=False)
        _mk_agente("Con QR", con_qr=True)

        resp = client.post("/api/qr/agentes/generar-qr-masivo", headers=self.admin_headers)
        body = resp.json()
        assert body["status"] == "success"
        assert body["total_sin_qr"] == 2
        assert body["generados"] + len(body["errores"]) == 2


class TestDashboardSinLinea:
    @classmethod
    def setup_class(cls):
        cls.admin_headers = {"Authorization": f"Bearer {_token('e2e_admin_dash', 'admin')}"}

    def setup_method(self):
        _clear_agent_tables()

    def test_dashboard_incluye_totals_sin_linea(self):
        resp = client.get("/api/dashboard/summary", headers=self.admin_headers)
        assert resp.status_code == 200
        totals = resp.json().get("totals", {})
        assert "sin_linea" in totals

    def test_dashboard_conteo_correcto(self):
        _mk_agente("Dash 1")
        _mk_agente("Dash 2")
        con_linea = _mk_agente("Dash con linea")
        _asignar_linea(con_linea.id, activa=True)

        resp = client.get("/api/dashboard/summary", headers=self.admin_headers)
        totals = resp.json().get("totals", {})
        assert totals["sin_linea"] >= 2

    def test_dashboard_alerta_action_section(self):
        _mk_agente("Dash alerta")
        resp = client.get("/api/dashboard/summary", headers=self.admin_headers)
        alerts = resp.json().get("alerts", [])
        assert any(a.get("action_section") == "estadoAgentes" for a in alerts)


class TestVistaEstadoPagoSinLinea:
    @classmethod
    def setup_class(cls):
        cls.admin_headers = {"Authorization": f"Bearer {_token('e2e_admin_estado_pago', 'admin')}"}

    def setup_method(self):
        _clear_agent_tables()

    def test_estado_pago_marca_sin_linea_cuando_no_hay_asignacion(self):
        _mk_agente("Estado Pago Sin Linea")
        resp = client.get("/api/qr/agentes/estado-pago", headers=self.admin_headers)
        assert resp.status_code == 200
        rows = resp.json().get("data", [])
        target = next((r for r in rows if r.get("nombre") == "Estado Pago Sin Linea"), None)
        assert target is not None
        assert target.get("linea_estado") == "SIN_LINEA"
        assert target.get("linea_id") is None
        assert target.get("extension_numero") in (None, "")


class TestQrStaticoYExportacion:
    @classmethod
    def setup_class(cls):
        cls.admin_headers = {"Authorization": f"Bearer {_token('e2e_admin_static_qr', 'admin')}"}

    def setup_method(self):
        _clear_agent_tables()

    def test_qr_agente_es_estatico_por_uuid(self):
        agente = _mk_agente("QR Estatico")

        first = client.get(f"/api/qr/agente/{agente.id}/qr", headers=self.admin_headers)
        second = client.get(f"/api/qr/agente/{agente.id}/qr", headers=self.admin_headers)

        assert first.status_code == 200
        assert second.status_code == 200

        data1 = first.json()["data"]
        data2 = second.json()["data"]
        assert data1["public_url"].endswith(f"/api/qr/public/verify/{agente.uuid}")
        assert data1["public_url"] == data2["public_url"]
        assert data1["qr_filename"] == data2["qr_filename"]
        assert data1["qr_mode"] == "static_uuid"

    def test_qr_estatico_refleja_linea_actual_del_servidor(self):
        agente = _mk_agente("QR Linea Dinamica")
        qr_resp = client.get(f"/api/qr/agente/{agente.id}/qr", headers=self.admin_headers)
        public_url = qr_resp.json()["data"]["public_url"]
        verify_path = urlparse(public_url).path

        before = client.get(verify_path)
        assert before.status_code == 200
        assert "SIN NUMERO ASIGNADO" in before.text

        _asignar_linea(agente.id, activa=True)

        after = client.get(verify_path)
        assert after.status_code == 200
        assert "NUMERO ASIGNADO" in after.text
        assert f"555-{agente.id:06d}" in after.text

    def test_exportacion_pdf_por_lotes(self):
        _mk_agente("Export QR 1")
        _mk_agente("Export QR 2")

        resp = client.get("/api/qr/agentes/export/pdf?layout=labels", headers=self.admin_headers)
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/pdf")
        assert resp.content.startswith(b"%PDF")
        assert len(resp.content) > 1000

    def test_verificacion_no_marca_asignacion_solo_por_telefono(self):
        agente = _mk_agente("Solo Telefono")
        db = _db()
        try:
            row = db.query(DatoImportado).filter(DatoImportado.id == agente.id).first()
            row.telefono = "5511111111"
            db.add(row)
            db.commit()
        finally:
            db.close()

        verify = client.get(f"/api/qr/verificar/{agente.id}", headers=self.admin_headers)
        assert verify.status_code == 200
        body = verify.json()
        assert body["agente"]["tiene_asignacion"] is False
        assert body["verificacion"]["numero_asignado"] is False


class TestFrontendAssets:
    def test_index_tiene_menu_y_seccion(self):
        html = open(_INDEX_HTML, encoding="utf-8").read()
        assert "estadoAgentesSection" in html
        assert "estadoAgentesMenuBadge" in html
        assert "loadSection('estadoAgentes'" in html

    def test_index_tiene_controles(self):
        html = open(_INDEX_HTML, encoding="utf-8").read()
        assert "estadoAgentesSearch" in html
        assert "estadoAgentesContainer" in html
        assert "generarQRMasivo()" in html
        assert "lineasSection" in html
        assert "lineasGestionContainer" in html
        assert "guardarLineaGestion(event)" in html
        assert "deudaManualPanel" in html
        assert "aplicarDeudaManualAgente()" in html
        assert "qrExportIds" in html
        assert "qrExportLayout" in html
        assert "serverVersionInfo" in html

    def test_js_tiene_funciones(self):
        js = open(_MAIN_JS, encoding="utf-8").read()
        assert "async function cargarEstadoAgentes" in js
        assert "async function generarQRMasivo" in js
        assert "async function generarQRAgenteIndividual" in js
        assert "async function guardarLineaGestion" in js
        assert "async function cargarLineasGestion" in js
        assert "async function aplicarDeudaManualAgente" in js
        assert "async function consultarDeudaManualAgente" in js
        assert "async function exportarQRLote" in js
        assert "async function loadServerVersionInfo" in js

    def test_js_tiene_wiring_menu_dashboard(self):
        js = open(_MAIN_JS, encoding="utf-8").read()
        assert "case 'estadoAgentes'" in js
        assert "case 'lineas'" in js
        assert "lineas: canCapture()" in js
        assert "estadoAgentes: canCapture()" in js
        assert "totals.sin_linea" in js

    def test_css_tiene_estilos_sin_linea(self):
        css = open(_STYLE_CSS, encoding="utf-8").read()
        assert ".row-sin-linea" in css
        assert ".menu-badge-warning" in css
        assert ".estado-agentes-banner" in css
        assert ".btn-warning" in css


class TestLineasGestionDebugE2E:
    @classmethod
    def setup_class(cls):
        cls.capture_headers = {"Authorization": f"Bearer {_token('e2e_capture_lineas', 'capture')}"}
        cls.admin_headers = {"Authorization": f"Bearer {_token('e2e_admin_lineas', 'admin')}"}

    def setup_method(self):
        _clear_agent_tables()

    def test_debug_flujo_lineas_crear_editar_asignar_y_listar(self):
        agente = _mk_agente("Debug Lineas")

        crear = client.post(
            "/api/qr/lineas",
            headers=self.capture_headers,
            json={
                "numero": "7771001",
                "tipo": "MANUAL",
                "descripcion": "Linea debug inicial",
                "sincronizar": False,
            },
        )
        assert crear.status_code == 200, crear.text
        linea = crear.json()["data"]
        linea_id = linea["id"]

        editar = client.put(
            f"/api/qr/lineas/{linea_id}",
            headers=self.capture_headers,
            json={
                "numero": "7771001",
                "tipo": "VOIP",
                "descripcion": "Linea debug editada",
            },
        )
        assert editar.status_code == 200, editar.text
        assert editar.json()["data"]["tipo"] == "VOIP"

        asignar = client.post(
            f"/api/qr/lineas/{linea_id}/asignar",
            headers=self.capture_headers,
            json={"agente_id": agente.id},
        )
        assert asignar.status_code == 200, asignar.text

        ocupadas = client.get("/api/qr/lineas?estado=ocupadas", headers=self.capture_headers)
        assert ocupadas.status_code == 200, ocupadas.text
        rows = ocupadas.json().get("data", [])
        debug_row = next((r for r in rows if r.get("id") == linea_id), None)
        print("DEBUG lineas ocupadas:", rows)
        assert debug_row is not None
        assert debug_row.get("agente", {}).get("id") == agente.id

        liberar = client.post(f"/api/qr/lineas/{linea_id}/liberar", headers=self.admin_headers, json={})
        assert liberar.status_code == 200, liberar.text

        libres = client.get("/api/qr/lineas?estado=libres", headers=self.capture_headers)
        assert libres.status_code == 200, libres.text
        libres_rows = libres.json().get("data", [])
        debug_libre = next((r for r in libres_rows if r.get("id") == linea_id), None)
        print("DEBUG lineas libres:", libres_rows)
        assert debug_libre is not None


class TestDeudaManualE2E:
    @classmethod
    def setup_class(cls):
        cls.admin_headers = {"Authorization": f"Bearer {_token('e2e_admin_deuda_manual', 'admin')}"}

    def setup_method(self):
        _clear_agent_tables()

    def test_control_manual_deuda_consulta_aplica_y_limpia(self):
        agente = _mk_agente("Deuda Manual")

        inicial = client.get(f"/api/qr/agentes/{agente.id}/deuda-manual", headers=self.admin_headers)
        assert inicial.status_code == 200, inicial.text
        data_inicial = inicial.json().get("data", {})
        assert float(data_inicial.get("ajuste_manual_deuda") or 0) == 0.0

        saldo_objetivo = client.put(
            f"/api/qr/agentes/{agente.id}/deuda-manual",
            headers=self.admin_headers,
            json={"modo": "saldo_objetivo", "monto": 240},
        )
        assert saldo_objetivo.status_code == 200, saldo_objetivo.text
        data_saldo = saldo_objetivo.json().get("data", {})
        assert float(data_saldo.get("saldo_acumulado") or 0) >= 239.99
        assert float(data_saldo.get("ajuste_manual_deuda") or 0) >= 239.99

        verificacion = client.get(f"/api/qr/verificar/{agente.id}", headers=self.admin_headers)
        assert verificacion.status_code == 200, verificacion.text
        ver = verificacion.json().get("verificacion", {})
        assert float(ver.get("ajuste_manual_deuda") or 0) >= 239.99

        ajuste_directo = client.put(
            f"/api/qr/agentes/{agente.id}/deuda-manual",
            headers=self.admin_headers,
            json={"modo": "ajuste", "monto": 125},
        )
        assert ajuste_directo.status_code == 200, ajuste_directo.text
        data_ajuste = ajuste_directo.json().get("data", {})
        assert abs(float(data_ajuste.get("ajuste_manual_deuda") or 0) - 125.0) < 0.01

        limpiar = client.put(
            f"/api/qr/agentes/{agente.id}/deuda-manual",
            headers=self.admin_headers,
            json={"modo": "ajuste", "monto": 0},
        )
        assert limpiar.status_code == 200, limpiar.text
        data_limpio = limpiar.json().get("data", {})
        assert abs(float(data_limpio.get("ajuste_manual_deuda") or 0)) < 0.01
