"""E2E de la funcionalidad Sin Linea."""

import json
import os
import uuid
from datetime import date, datetime, timedelta
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models as _all_models  # noqa: F401
from app.database.orm import Base, get_db
from app.models import (
    AgenteLineaAsignacion,
    CobranzaSemanalSnapshot,
    DatoImportado,
    LineaTelefonica,
    PagoSemanal,
)
from app.security import create_access_token
from app.utils.pagos import monday_of_week
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


def _bind_test_db_override() -> None:
    # Test modules share a single FastAPI app instance; enforce our override
    # to avoid cross-module DB leakage when other suites replace get_db.
    app.dependency_overrides[get_db] = override_get_db


_bind_test_db_override()
client = TestClient(app, raise_server_exceptions=False, base_url="https://testserver:8443")

_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
_INDEX_HTML = os.path.join(_REPO_ROOT, "web", "index.html")
_MAIN_JS = os.path.join(_REPO_ROOT, "web", "js", "main.js")
_API_CLIENT_JS = os.path.join(_REPO_ROOT, "web", "js", "api-client.js")
_QR_COBROS_JS = os.path.join(_REPO_ROOT, "web", "js", "qrCobros.js")
_MOBILE_JS = os.path.join(_REPO_ROOT, "web", "m", "mobile.js")
_SMART_IMPORT_JS = os.path.join(_REPO_ROOT, "web", "js", "smartImport.js")
_STYLE_CSS = os.path.join(_REPO_ROOT, "web", "css", "style.css")


def _db() -> Session:
    _bind_test_db_override()
    return TestingSessionLocal()


def _clear_agent_tables() -> None:
    _bind_test_db_override()
    db = _db()
    try:
        db.query(CobranzaSemanalSnapshot).delete()
        db.query(PagoSemanal).delete()
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


class TestQrAgentesBusquedaYVoip:
    @classmethod
    def setup_class(cls):
        cls.capture_headers = {"Authorization": f"Bearer {_token('e2e_capture_agentes', 'capture')}"}

    def setup_method(self):
        _clear_agent_tables()

    def test_busqueda_qr_agentes_por_nombre_y_alias(self):
        db = _db()
        try:
            a1 = DatoImportado(
                nombre="Cristian Gomez",
                es_activo=True,
                datos_adicionales=json.dumps({"alias": "Cris", "numero_voip": "1001"}),
            )
            a2 = DatoImportado(
                nombre="Mario Ruiz",
                es_activo=True,
                datos_adicionales=json.dumps({"alias": "Mruiz", "numero_voip": "2002"}),
            )
            db.add_all([a1, a2])
            db.commit()
        finally:
            db.close()

        resp_nombre = client.get("/api/qr/agentes?search=Cristian", headers=self.capture_headers)
        assert resp_nombre.status_code == 200, resp_nombre.text
        data_nombre = resp_nombre.json().get("data", [])
        assert any((row.get("nombre") or "") == "Cristian Gomez" for row in data_nombre)

        resp_alias = client.get("/api/qr/agentes?search=Cris", headers=self.capture_headers)
        assert resp_alias.status_code == 200, resp_alias.text
        data_alias = resp_alias.json().get("data", [])
        target = next((row for row in data_alias if (row.get("nombre") or "") == "Cristian Gomez"), None)
        assert target is not None
        assert target.get("alias") == "Cris"

    def test_qr_agentes_devuelve_numero_voip(self):
        db = _db()
        try:
            ag = DatoImportado(
                nombre="Agente Voip",
                es_activo=True,
                datos_adicionales=json.dumps({"alias": "VoipA", "numero_voip": "3333"}),
            )
            db.add(ag)
            db.commit()
            db.refresh(ag)
            ag_id = ag.id
        finally:
            db.close()

        resp = client.get("/api/qr/agentes?search=VoipA", headers=self.capture_headers)
        assert resp.status_code == 200, resp.text
        rows = resp.json().get("data", [])
        target = next((row for row in rows if row.get("id") == ag_id), None)
        assert target is not None
        assert target.get("numero_voip") == "3333"

    def test_busqueda_qr_agentes_por_id_y_fp(self):
        db = _db()
        try:
            ag = DatoImportado(
                nombre="Agente FP",
                es_activo=True,
                telefono="5551234567",
                datos_adicionales=json.dumps({"alias": "AFP", "fp": "FP-7788", "numero_voip": "7788"}),
            )
            db.add(ag)
            db.commit()
            db.refresh(ag)
            ag_id = ag.id
        finally:
            db.close()

        resp_id = client.get(f"/api/qr/agentes?search={ag_id}", headers=self.capture_headers)
        assert resp_id.status_code == 200, resp_id.text
        rows_id = resp_id.json().get("data", [])
        assert any(row.get("id") == ag_id for row in rows_id)

        resp_fp = client.get("/api/qr/agentes?search=FP-7788", headers=self.capture_headers)
        assert resp_fp.status_code == 200, resp_fp.text
        rows_fp = resp_fp.json().get("data", [])
        target_fp = next((row for row in rows_fp if row.get("id") == ag_id), None)
        assert target_fp is not None
        assert (target_fp.get("datos_adicionales") or {}).get("fp") == "FP-7788"

    def test_qr_agentes_lineas_incluye_id_y_linea_id(self):
        db = _db()
        try:
            ag = DatoImportado(nombre="Agente Lineas", es_activo=True)
            db.add(ag)
            db.flush()

            linea = LineaTelefonica(numero="5550101001", tipo="EXT_PBX", es_activa=True)
            db.add(linea)
            db.flush()

            db.add(AgenteLineaAsignacion(agente_id=ag.id, linea_id=linea.id, es_activa=True))
            db.commit()
            ag_id = ag.id
            linea_id = linea.id
        finally:
            db.close()

        resp = client.get("/api/qr/agentes?search=Agente%20Lineas", headers=self.capture_headers)
        assert resp.status_code == 200, resp.text
        rows = resp.json().get("data", [])
        target = next((row for row in rows if row.get("id") == ag_id), None)
        assert target is not None
        lineas = target.get("lineas") or []
        assert lineas, "El agente debe incluir lineas activas"
        assert lineas[0].get("linea_id") == linea_id
        assert lineas[0].get("id") == linea_id


class TestQrExportListado:
    @classmethod
    def setup_class(cls):
        cls.capture_headers = {"Authorization": f"Bearer {_token('e2e_capture_export_qr', 'capture')}"}

    def setup_method(self):
        _clear_agent_tables()

    def test_listado_export_incluye_agentes_sin_qr_code(self):
        agente = _mk_agente("Exportable Sin QRCode", activo=True, con_qr=False)

        db = _db()
        try:
            row = db.query(DatoImportado).filter(DatoImportado.id == agente.id).first()
            # Asegura regresion historica: sin qr_code persistido
            row.qr_code = None
            db.add(row)
            db.commit()
        finally:
            db.close()

        resp = client.get(
            "/api/qr/agentes/sin-imprimir?estado=todos&solo_activos=true",
            headers=self.capture_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        rows = body.get("agentes", [])
        assert any(r.get("id") == agente.id for r in rows)


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

    def test_estado_pago_marca_pendiente_si_saldo_acumulado_es_mayor_a_cero(self):
        agente = _mk_agente("Estado Pago Saldo Pendiente")
        _asignar_linea(agente.id, activa=True)

        semana_ref = monday_of_week(date.today())
        db = _db()
        try:
            db.add(
                PagoSemanal(
                    agente_id=agente.id,
                    telefono="5551112233",
                    numero_voip="1001",
                    semana_inicio=semana_ref,
                    monto=1.0,
                    pagado=True,
                )
            )
            db.commit()
        finally:
            db.close()

        resp = client.get(
            f"/api/qr/agentes/estado-pago?semana={semana_ref.isoformat()}",
            headers=self.admin_headers,
        )
        assert resp.status_code == 200
        rows = resp.json().get("data", [])
        target = next((r for r in rows if r.get("agente_id") == agente.id), None)
        assert target is not None
        assert target.get("estado_pago") == "Pendiente de Pago"
        assert bool(target.get("pagado")) is False


class TestTotalesCobranzaQr:
    @classmethod
    def setup_class(cls):
        cls.admin_headers = {"Authorization": f"Bearer {_token('e2e_admin_totales_cobro', 'admin')}"}

    def setup_method(self):
        _clear_agent_tables()

    def test_totales_cobranza_por_fecha_y_semana(self):
        semana_ref = monday_of_week(date.today())
        fecha_ref = semana_ref + timedelta(days=2)

        agente_1 = _mk_agente("Cobro Diario 1")
        agente_2 = _mk_agente("Cobro Diario 2")
        agente_3 = _mk_agente("Cobro Otra Semana")

        db = _db()
        try:
            db.add_all(
                [
                    PagoSemanal(
                        agente_id=agente_1.id,
                        telefono="5511110001",
                        numero_voip="1001",
                        semana_inicio=semana_ref,
                        monto=300.0,
                        pagado=True,
                        fecha_pago=datetime(fecha_ref.year, fecha_ref.month, fecha_ref.day, 10, 30, 0),
                    ),
                    PagoSemanal(
                        agente_id=agente_2.id,
                        telefono="5511110002",
                        numero_voip="1002",
                        semana_inicio=semana_ref,
                        monto=150.0,
                        pagado=True,
                        fecha_pago=datetime(fecha_ref.year, fecha_ref.month, fecha_ref.day, 14, 45, 0),
                    ),
                    PagoSemanal(
                        agente_id=agente_3.id,
                        telefono="5511110003",
                        numero_voip="1003",
                        semana_inicio=semana_ref - timedelta(days=7),
                        monto=200.0,
                        pagado=True,
                        fecha_pago=datetime(fecha_ref.year, fecha_ref.month, fecha_ref.day, 18, 0, 0),
                    ),
                ]
            )
            db.commit()
        finally:
            db.close()

        resp = client.get(
            f"/api/qr/pagos/totales?fecha={fecha_ref.isoformat()}&semana={semana_ref.isoformat()}",
            headers=self.admin_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body.get("status") == "success"

        data = body.get("data") or {}
        assert data.get("fecha") == fecha_ref.isoformat()
        assert data.get("semana_inicio") == semana_ref.isoformat()

        # Diario suma pagos por fecha (sin importar semana operativa)
        assert float(data.get("total_pagado_dia") or 0) == pytest.approx(650.0)
        assert int(data.get("pagos_registrados_dia") or 0) == 3

        # Semanal suma pagos asociados a la semana operativa seleccionada
        assert float(data.get("total_pagado_semana") or 0) == pytest.approx(450.0)
        assert int(data.get("pagos_registrados_semana") or 0) == 2


class TestReporteSemanalGlobal:
    @classmethod
    def setup_class(cls):
        cls.admin_headers = {"Authorization": f"Bearer {_token('e2e_admin_reporte_global', 'admin')}"}

    def setup_method(self):
        _clear_agent_tables()

    def test_reporte_semanal_expone_totales_financieros_y_discrepancias(self):
        semana_ref = monday_of_week(date.today())
        agente_1 = _mk_agente("Reporte Global 1")
        agente_2 = _mk_agente("Reporte Global 2")
        _asignar_linea(agente_1.id, activa=True)
        _asignar_linea(agente_2.id, activa=True)

        db = _db()
        try:
            db.add_all(
                [
                    PagoSemanal(
                        agente_id=agente_1.id,
                        telefono="5512000001",
                        numero_voip="1101",
                        semana_inicio=semana_ref,
                        monto=300.0,
                        pagado=True,
                        fecha_pago=datetime.utcnow(),
                    ),
                    PagoSemanal(
                        agente_id=agente_1.id,
                        telefono="5512000001",
                        numero_voip="1101",
                        semana_inicio=semana_ref,
                        monto=50.0,
                        pagado=True,
                        fecha_pago=datetime.utcnow(),
                    ),
                    PagoSemanal(
                        agente_id=agente_2.id,
                        telefono="5512000002",
                        numero_voip="1102",
                        semana_inicio=semana_ref,
                        monto=100.0,
                        pagado=True,
                        fecha_pago=datetime.utcnow(),
                    ),
                ]
            )
            db.commit()
        finally:
            db.close()

        resp = client.get(
            f"/api/qr/reporte-semanal?semana={semana_ref.isoformat()}",
            headers=self.admin_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body.get("status") == "success"

        tot = body.get("totales") or {}
        assert float(tot.get("deuda_total_global") or 0) > 0
        assert float(tot.get("total_abonado_global") or 0) >= 0
        assert float(tot.get("saldo_global") or 0) >= 0
        assert float(tot.get("monto_semana_ledger") or 0) == pytest.approx(450.0)
        assert float(tot.get("discrepancia_semana") or 0) != pytest.approx(0.0)

        discrepancias = body.get("discrepancias") or []
        assert any(d.get("codigo") == "PAGOS_DUPLICADOS_AGENTE_SEMANA" for d in discrepancias)

    def test_reporte_semanal_persiste_snapshot_balance_en_bd(self):
        semana_ref = monday_of_week(date.today())
        agente = _mk_agente("Snapshot Balance")
        _asignar_linea(agente.id, activa=True)

        db = _db()
        try:
            db.add(
                PagoSemanal(
                    agente_id=agente.id,
                    telefono="5513000001",
                    numero_voip="1201",
                    semana_inicio=semana_ref,
                    monto=250.0,
                    pagado=True,
                    fecha_pago=datetime.utcnow(),
                )
            )
            db.commit()
        finally:
            db.close()

        resp = client.get(
            f"/api/qr/reporte-semanal?semana={semana_ref.isoformat()}",
            headers=self.admin_headers,
        )
        assert resp.status_code == 200, resp.text
        snapshot = (resp.json() or {}).get("snapshot") or {}
        assert snapshot.get("id")
        assert snapshot.get("semana_inicio") == semana_ref.isoformat()

        db = _db()
        try:
            row = (
                db.query(CobranzaSemanalSnapshot)
                .filter(CobranzaSemanalSnapshot.id == int(snapshot["id"]))
                .first()
            )
            assert row is not None
            assert row.semana_inicio == semana_ref
            assert float(row.total_abonado_global or 0) >= 0
            assert float(row.saldo_global or 0) >= 0
        finally:
            db.close()


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

        resp_oficio = client.get("/api/qr/agentes/export/pdf?layout=oficio", headers=self.admin_headers)
        assert resp_oficio.status_code == 200
        assert resp_oficio.headers["content-type"].startswith("application/pdf")
        assert resp_oficio.content.startswith(b"%PDF")
        assert len(resp_oficio.content) > 1000

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


class TestAltaManualAliasNullE2E:
    @classmethod
    def setup_class(cls):
        cls.capture_headers = {"Authorization": f"Bearer {_token('e2e_capture_alias_null', 'capture')}"}

    def setup_method(self):
        _clear_agent_tables()

    def test_alta_manual_acepta_alias_sin_nombre_y_persiste(self):
        resp = client.post(
            "/api/qr/agentes/manual",
            headers=self.capture_headers,
            json={
                "nombre": "",
                "alias": "AliasPrincipal",
                "modo_asignacion": "ninguna",
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()["data"]
        assert body["agente_id"] > 0

        db = _db()
        try:
            row = db.query(DatoImportado).filter(DatoImportado.id == body["agente_id"]).first()
            assert row is not None
            assert row.es_activo is True
            assert (row.nombre is None) or (str(row.nombre).strip() == "")
            extras = json.loads(row.datos_adicionales or "{}")
            assert extras.get("alias") == "AliasPrincipal"
        finally:
            db.close()

    def test_alta_manual_interpreta_texto_null_como_nulo(self):
        resp = client.post(
            "/api/qr/agentes/manual",
            headers=self.capture_headers,
            json={
                "nombre": "NULL",
                "alias": "AliasNull",
                "ubicacion": "NULL",
                "fp": "NULL",
                "modo_asignacion": "ninguna",
            },
        )
        assert resp.status_code == 200, resp.text
        agente_id = resp.json()["data"]["agente_id"]

        db = _db()
        try:
            row = db.query(DatoImportado).filter(DatoImportado.id == agente_id).first()
            assert row is not None
            assert (row.nombre is None) or (str(row.nombre).strip() == "")
            extras = json.loads(row.datos_adicionales or "{}")
            assert extras.get("alias") == "AliasNull"
            assert "ubicacion" not in extras
            assert "fp" not in extras
        finally:
            db.close()

    def test_listado_agentes_incluye_nombres_vacios_y_display_name_por_alias(self):
        agente = DatoImportado(nombre=None, es_activo=True, datos_adicionales=json.dumps({"alias": "AliasListado"}))
        db = _db()
        try:
            db.add(agente)
            db.commit()
            db.refresh(agente)
            agente_id = agente.id
        finally:
            db.close()

        resp = client.get("/api/qr/agentes", headers=self.capture_headers)
        assert resp.status_code == 200, resp.text
        rows = resp.json().get("data", [])
        target = next((r for r in rows if r.get("id") == agente_id), None)
        assert target is not None
        assert target.get("alias") == "AliasListado"
        assert target.get("display_name") == "AliasListado"


class TestFrontendAssets:
    def test_index_tiene_menu_y_seccion(self):
        html = open(_INDEX_HTML, encoding="utf-8").read()
        assert "estadoAgentesSection" in html
        assert "estadoAgentesMenuBadge" in html
        assert "loadSection('estadoAgentes'" in html

    def test_index_tiene_controles(self):
        html = open(_INDEX_HTML, encoding="utf-8").read()
        assert 'js/app-utils.js' in html
        assert "estadoAgentesSearch" in html
        assert "estadoAgentesContainer" in html
        assert "generarQRMasivo()" in html
        assert "lineasSection" in html
        assert "lineasGestionContainer" in html
        assert "guardarLineaGestion(event)" in html
        assert "agenteLineaCategoriaSelect" in html
        assert "agenteLineaConexionSelect" in html
        assert "lineaAsignarCategoria" in html
        assert "lineaAsignarConexion" in html
        assert "deudaManualPanel" in html
        assert "aplicarDeudaManualAgente()" in html
        assert "qrExportListaAgentes" in html
        assert "qrExportLayout" in html
        assert "oficio" in html
        assert "serverVersionInfo" in html
        assert "miCuentaSection" in html
        assert "regAccountMode" in html
        assert "tempUsername" in html

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
        assert "function showAppAlert" in js
        assert "function getErrorMessage" in js

    def test_css_tiene_estilos_modal_alerta(self):
        css = open(_STYLE_CSS, encoding="utf-8").read()
        assert ".app-alert-backdrop" in css
        assert ".app-alert-modal" in css
        assert ".app-alert-title" in css

    def test_js_tiene_wiring_menu_dashboard(self):
        js = open(_MAIN_JS, encoding="utf-8").read()
        assert "case 'estadoAgentes'" in js
        assert "case 'lineas'" in js
        assert "lineas: canCapture()" in js
        assert "estadoAgentes: canCapture()" in js
        assert "totals.sin_linea" in js
        assert "case 'miCuenta'" in js
        assert "return ['miCuenta'].includes(section);" in js

    def test_js_tiene_autoservicio_limitado(self):
        js = open(_MAIN_JS, encoding="utf-8").read()
        api_js = open(_API_CLIENT_JS, encoding="utf-8").read()
        assert "async function cargarResumenAutoservicio()" in js
        assert "async function solicitarCuentaNormalLimitada()" in js
        assert "isLimitedViewer()" in js
        assert "registrar-temporal" in js
        assert "async registrarTemporal(" in api_js
        assert "async getSelfServiceResumen()" in api_js

    def test_lineas_ui_normaliza_linea_id_en_acciones(self):
        js = open(_MAIN_JS, encoding="utf-8").read()
        assert "function resolveLineaId(linea)" in js
        assert "const safeLineaId = resolveLineaId(linea);" in js
        assert "if (!safeLineaId) {" in js
        assert "onclick=\"liberarLinea(${safeLineaId})\"" in js

    def test_api_client_bloquea_segmentos_invalidos_en_endpoint(self):
        api_js = open(_API_CLIENT_JS, encoding="utf-8").read()
        assert "_containsInvalidPathSegment(endpoint)" in api_js
        assert "segment === 'undefined' || segment === 'null' || segment === 'nan'" in api_js
        assert "throw new Error('Validación fallida: endpoint inválido')" in api_js

    def test_qr_api_listados_soportan_paginacion_basica(self):
        qr_api = open(os.path.join(_REPO_ROOT, "backend", "app", "api", "qr.py"), encoding="utf-8").read()
        assert "def listar_agentes_sin_linea(" in qr_api
        assert "skip: int = Query(0, ge=0)" in qr_api
        assert "limit: int = Query(500, ge=1, le=1000)" in qr_api
        assert ".offset(skip).limit(limit)" in qr_api
        assert "LIMIT :limit" in qr_api
        assert "OFFSET :skip" in qr_api

    def test_qr_scan_tiene_continuidad_y_antirebote(self):
        js = open(_MAIN_JS, encoding="utf-8").read()
        assert "const QR_SCAN_DUPLICATE_WINDOW_MS" in js
        assert "let qrDecodeInFlight" in js
        assert "function isQrScannerRunning()" in js
        assert "if (qrDecodeInFlight)" in js
        assert "normalizedCode === qrLastDecodedText" in js
        assert "await detenerEscanerQR();" in js

    def test_qr_scan_abono_permite_monto_editable(self):
        js = open(_MAIN_JS, encoding="utf-8").read()
        assert "showQuickAbonoModal" in js
        assert "Registrar Abono Parcial" in js
        assert "pagado: mode === 'liquidar'" in js
        assert "qr-abono-feedback" in js
        assert "acceptBtn.disabled" in js
        assert "excede el saldo acumulado" in js

    def test_css_modal_abono_es_responsive_en_movil(self):
        css = open(_STYLE_CSS, encoding="utf-8").read()
        assert ".qr-abono-modal" in css
        assert ".qr-abono-kpis" in css
        assert ".qr-abono-actions" in css

    def test_qr_toggle_camera_espera_inicio_real(self):
        js = open(_QR_COBROS_JS, encoding="utf-8").read()
        assert "async function qrToggleCamera()" in js
        assert "await iniciarEscanerQR()" in js
        assert "window.isQrScannerRunning" in js

    def test_mobile_qr_scanner_tiene_loader_y_guardas_de_arranque(self):
        js = open(_MOBILE_JS, encoding="utf-8").read()
        assert "let qrScannerStartInFlight = false;" in js
        assert "let qrScannerStopInFlight = false;" in js
        assert "async function ensureQrScannerLibrary()" in js
        assert "https://unpkg.com/html5-qrcode@2.3.8" in js
        assert "https://cdn.jsdelivr.net/npm/html5-qrcode@2.3.8" in js
        assert "if (qrScannerInstance || qrScannerStartInFlight || qrScannerStopInFlight)" in js

    def test_mobile_android_usa_sesion_efimera_para_token(self):
        api_js = open(_API_CLIENT_JS, encoding="utf-8").read()
        mobile_js = open(_MOBILE_JS, encoding="utf-8").read()

        assert "_detectPreferredPersistence()" in api_js
        assert "return window.PhantomAndroid ? 'session' : 'local';" in api_js
        assert "setAuthPersistence(mode = 'local')" in api_js
        assert "if (normalized === 'session') {" in api_js
        assert "localStorage.removeItem('authToken');" in api_js

        assert "function getMobileSessionStorage()" in mobile_js
        assert "return isInsideNativeApp() ? sessionStorage : localStorage;" in mobile_js
        assert "mobileToken = apiClient.getToken() || '';" in mobile_js

    def test_smart_import_ui_tabs_y_rollback_wiring(self):
        index_html = open(_INDEX_HTML, encoding="utf-8").read()
        smart_js = open(_SMART_IMPORT_JS, encoding="utf-8").read()

        assert "id=\"siTabClassicBtn\"" in index_html
        assert "id=\"siTabSmartBtn\"" in index_html
        assert "id=\"importClassicTab\"" in index_html
        assert "id=\"importSmartTab\"" in index_html
        assert "id=\"siRollbackOnErrors\"" in index_html

        assert "const isSmart = tab === 'smart' || tab === 'intelligent';" in smart_js
        assert "document.getElementById('siTabClassicBtn')" in smart_js
        assert "document.getElementById('siTabSmartBtn')" in smart_js
        assert "formData.append('rollback_si_hay_errores'" in smart_js

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
                "categoria_linea": "FIJO",
                "estado_conexion": "CONECTADA",
                "fecha_ultimo_uso": "2026-01-15T10:30:00",
                "sincronizar": False,
            },
        )
        assert crear.status_code == 200, crear.text
        linea = crear.json()["data"]
        linea_id = linea["id"]
        assert linea["categoria_linea"] == "FIJO"
        assert linea["estado_conexion"] == "CONECTADA"
        assert str(linea.get("fecha_ultimo_uso") or "").startswith("2026-01-15T10:30:00")

        editar = client.put(
            f"/api/qr/lineas/{linea_id}",
            headers=self.capture_headers,
            json={
                "numero": "7771001",
                "tipo": "VOIP",
                "descripcion": "Linea debug editada",
                "categoria_linea": "MOVIL",
                "estado_conexion": "DESCONECTADA",
                "fecha_ultimo_uso": "2026-01-20",
            },
        )
        assert editar.status_code == 200, editar.text
        assert editar.json()["data"]["tipo"] == "VOIP"
        assert editar.json()["data"]["categoria_linea"] == "MOVIL"
        assert editar.json()["data"]["estado_conexion"] == "DESCONECTADA"
        assert str(editar.json()["data"].get("fecha_ultimo_uso") or "").startswith("2026-01-20T00:00:00")

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
        assert debug_row.get("categoria_linea") == "MOVIL"
        assert debug_row.get("estado_conexion") == "DESCONECTADA"
        assert str(debug_row.get("fecha_ultimo_uso") or "").startswith("2026-01-20T00:00:00")

        liberar = client.post(f"/api/qr/lineas/{linea_id}/liberar", headers=self.admin_headers, json={})
        assert liberar.status_code == 200, liberar.text

        libres = client.get("/api/qr/lineas?estado=libres", headers=self.capture_headers)
        assert libres.status_code == 200, libres.text
        libres_rows = libres.json().get("data", [])
        debug_libre = next((r for r in libres_rows if r.get("id") == linea_id), None)
        print("DEBUG lineas libres:", libres_rows)
        assert debug_libre is not None

    def test_liberar_linea_rechaza_agente_id_invalido(self):
        agente = _mk_agente("Debug Invalid Agente ID")

        crear = client.post(
            "/api/qr/lineas",
            headers=self.capture_headers,
            json={
                "numero": "7771888",
                "tipo": "MANUAL",
                "descripcion": "Linea debug invalida payload",
                "sincronizar": False,
            },
        )
        assert crear.status_code == 200, crear.text
        linea_id = int(crear.json()["data"]["id"])

        asignar = client.post(
            f"/api/qr/lineas/{linea_id}/asignar",
            headers=self.capture_headers,
            json={"agente_id": agente.id},
        )
        assert asignar.status_code == 200, asignar.text

        liberar = client.post(
            f"/api/qr/lineas/{linea_id}/liberar",
            headers=self.admin_headers,
            json={"agente_id": "undefined"},
        )
        assert liberar.status_code == 400, liberar.text


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

    def test_permite_registrar_pago_con_adeudo_sin_linea_activa(self):
        agente = _mk_agente("Deuda Sin Linea")

        crear_adeudo = client.put(
            f"/api/qr/agentes/{agente.id}/deuda-manual",
            headers=self.admin_headers,
            json={"modo": "saldo_objetivo", "monto": 200},
        )
        assert crear_adeudo.status_code == 200, crear_adeudo.text

        semana_ref = monday_of_week(date.today())
        pago = client.post(
            "/api/qr/pagos",
            headers=self.admin_headers,
            json={
                "agente_id": agente.id,
                "semana_inicio": semana_ref.isoformat(),
                "monto": 200,
                "pagado": True,
                "observaciones": "Liquidacion sin linea",
            },
        )
        assert pago.status_code == 200, pago.text
        body = pago.json()
        assert float(body.get("abono_registrado") or 0) == pytest.approx(200.0)
        assert float(body.get("saldo_acumulado") or 0) <= 0.01

    def test_editar_pago_refresca_recibo_para_reimpresion(self):
        agente = _mk_agente("Recibo Editable")
        semana_ref = monday_of_week(date.today())

        pago_resp = client.post(
            "/api/qr/pagos",
            headers=self.admin_headers,
            json={
                "agente_id": agente.id,
                "semana_inicio": semana_ref.isoformat(),
                "monto": 120,
                "pagado": False,
                "observaciones": "abono inicial",
            },
        )
        assert pago_resp.status_code == 200, pago_resp.text
        pago_data = pago_resp.json()
        pago_id = int(pago_data.get("id") or 0)
        token = ((pago_data.get("recibo") or {}).get("token") or "").strip()
        assert pago_id > 0
        assert token

        edit_resp = client.put(
            f"/api/qr/pagos/{pago_id}",
            headers=self.admin_headers,
            json={"monto": 300, "pagado": True, "observaciones": "liquidado admin"},
        )
        assert edit_resp.status_code == 200, edit_resp.text
        edit_data = edit_resp.json().get("data", {})
        assert abs(float(edit_data.get("monto") or 0) - 300.0) < 0.01
        assert bool(edit_data.get("pagado")) is True
        token_editado = ((edit_data.get("recibo") or {}).get("token") or "").strip()
        assert token_editado

        recibo_resp = client.get(f"/api/qr/recibos/{token_editado}", headers=self.admin_headers)
        assert recibo_resp.status_code == 200, recibo_resp.text
        recibo_data = recibo_resp.json().get("data", {})
        assert abs(float(recibo_data.get("monto") or 0) - 300.0) < 0.01
        assert bool(recibo_data.get("pagado")) is True

    def test_recibo_incluye_abono_y_saldo_al_reimprimir(self):
        agente = _mk_agente("Recibo Saldo")
        semana_ref = monday_of_week(date.today())

        pago_resp = client.post(
            "/api/qr/pagos",
            headers=self.admin_headers,
            json={
                "agente_id": agente.id,
                "semana_inicio": semana_ref.isoformat(),
                "monto": 200,
                "pagado": False,
                "observaciones": "abono para recibo",
            },
        )
        assert pago_resp.status_code == 200, pago_resp.text
        token = ((pago_resp.json().get("recibo") or {}).get("token") or "").strip()
        assert token

        recibo_resp = client.get(f"/api/qr/recibos/{token}", headers=self.admin_headers)
        assert recibo_resp.status_code == 200, recibo_resp.text
        data = recibo_resp.json().get("data", {})
        assert abs(float(data.get("abono_aplicado") or 0) - 200.0) < 0.01
        assert "saldo_acumulado" in data
        assert "deuda_total" in data
        assert "total_abonado" in data

    def test_admin_puede_revertir_pago_y_actualiza_recibo(self):
        agente = _mk_agente("Reversion Pago")
        semana_ref = monday_of_week(date.today())

        pago_resp = client.post(
            "/api/qr/pagos",
            headers=self.admin_headers,
            json={
                "agente_id": agente.id,
                "semana_inicio": semana_ref.isoformat(),
                "monto": 250,
                "pagado": False,
                "observaciones": "pago de prueba a revertir",
            },
        )
        assert pago_resp.status_code == 200, pago_resp.text
        pago_data = pago_resp.json()
        pago_id = int(pago_data.get("id") or 0)
        assert pago_id > 0

        revertir = client.post(
            f"/api/qr/pagos/{pago_id}/revertir",
            headers=self.admin_headers,
            json={"motivo": "Pago de prueba"},
        )
        assert revertir.status_code == 200, revertir.text
        revert_data = (revertir.json() or {}).get("data") or {}
        assert abs(float(revert_data.get("monto_revertido") or 0) - 250.0) < 0.01
        assert abs(float(revert_data.get("monto_actual") or 0)) < 0.01
        assert bool(revert_data.get("pagado")) is False
        assert bool(revert_data.get("revertido")) is True

        token = ((revert_data.get("recibo") or {}).get("token") or "").strip()
        assert token
        recibo_resp = client.get(f"/api/qr/recibos/{token}", headers=self.admin_headers)
        assert recibo_resp.status_code == 200, recibo_resp.text
        recibo_data = (recibo_resp.json() or {}).get("data") or {}
        assert abs(float(recibo_data.get("monto") or 0)) < 0.01
        assert bool(recibo_data.get("pagado")) is False
        assert str(recibo_data.get("estado_pago") or "").lower() == "cancelado"

    def test_revertir_pago_ya_en_cero_regresa_error(self):
        agente = _mk_agente("Reversion Cero")
        semana_ref = monday_of_week(date.today())

        pago_resp = client.post(
            "/api/qr/pagos",
            headers=self.admin_headers,
            json={
                "agente_id": agente.id,
                "semana_inicio": semana_ref.isoformat(),
                "monto": 100,
                "pagado": False,
                "observaciones": "abono para reversa",
            },
        )
        assert pago_resp.status_code == 200, pago_resp.text
        pago_id = int((pago_resp.json() or {}).get("id") or 0)
        assert pago_id > 0

        first = client.post(
            f"/api/qr/pagos/{pago_id}/revertir",
            headers=self.admin_headers,
            json={"motivo": "primera reversa"},
        )
        assert first.status_code == 200, first.text

        second = client.post(
            f"/api/qr/pagos/{pago_id}/revertir",
            headers=self.admin_headers,
            json={"motivo": "segunda reversa"},
        )
        assert second.status_code == 409, second.text
