"""Tests de seguridad y autenticación."""

import pytest
import uuid
import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database.orm import Base, get_db
from app.database.repositorios import RepositorioUsuario
from app.models import Usuario
from app.schemas import UsuarioCrear
from app.security import create_access_token
from app import security as security_module
from app.api import export as export_api
from app.config import config as app_config
from main import app

# DB de test en memoria
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)
# TestClient con base HTTPS para evitar que los redireccionamientos HTTP→HTTPS descarten el header Authorization
https_client = TestClient(app, base_url="https://testserver:8443")


class TestAutenticacion:
    """Tests de autenticación."""
    
    def test_registrar_usuario(self):
        """Test registrar nuevo usuario."""
        response = client.post(
            "/api/auth/registrar",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "TestPassword123!",
                "nombre_completo": "Test User"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
    
    def test_login_invalido(self):
        """Test login con credenciales inválidas."""
        response = client.post(
            "/api/auth/login",
            json={
                "username": "invalid",
                "password": "wrongpassword"
            }
        )
        assert response.status_code == 401
    
    def test_registrar_duplicado(self):
        """Test registrar usuario duplicado."""
        usuario = {
            "username": "duplicate",
            "email": "duplicate@example.com",
            "password": "TestPassword123!",
            "nombre_completo": "Duplicate"
        }
        
        # Primer registro
        response1 = client.post("/api/auth/registrar", json=usuario)
        assert response1.status_code == 200
        
        # Segundo registro (debe fallar)
        response2 = client.post("/api/auth/registrar", json=usuario)
        assert response2.status_code == 400

    def test_registro_publico_no_permite_elevacion_privilegios(self):
        """El registro abierto no debe permitir crear admin/super_admin."""
        suffix = uuid.uuid4().hex[:8]
        response = client.post(
            "/api/auth/registrar",
            json={
                "username": f"public_{suffix}",
                "email": f"public_{suffix}@example.com",
                "password": "TestPassword123!",
                "nombre_completo": "Public User",
                "rol": "super_admin",
                "es_admin": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["rol"] == "viewer"
        assert data["es_admin"] is False


class TestDatos:
    """Tests de endpoints de datos."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup antes de cada test."""
        db = TestingSessionLocal()
        repo_usuario = RepositorioUsuario(db)
        if not repo_usuario.obtener_por_username("testuser_datos"):
            repo_usuario.crear(
                UsuarioCrear(
                    username="testuser_datos",
                    email="testdatos@example.com",
                    password="TestPassword123!",
                    nombre_completo="Test Datos",
                    rol="capture",
                    es_admin=False,
                )
            )
        db.close()

        # Login
        login_response = https_client.post(
            "/api/auth/login",
            json={"username": "testuser_datos", "password": "TestPassword123!"}
        )
        assert login_response.status_code == 200
        self.token = login_response.json()["access_token"]

    def test_listar_datos(self):
        """Test listar datos."""
        headers = {"Authorization": f"Bearer {self.token}"}
        response = https_client.get("/api/datos/", headers=headers)
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    def test_crear_dato(self):
        """Test crear dato."""
        headers = {"Authorization": f"Bearer {self.token}"}
        response = https_client.post(
            "/api/datos/",
            headers=headers,
            json={
                "nombre": "Juan Perez",
                "email": "juan@example.com",
                "telefono": "123456789",
                "empresa": "TechCorp"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["nombre"] == "Juan Perez"


class TestSalud:
    """Tests de endpoints de sistema."""
    
    def test_health_check(self):
        """Test health check."""
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestSuperAdminPermisos:
    """Tests de permisos para creación de super_admin."""

    def _token(self, *, user_id: int, username: str, role: str) -> str:
        return create_access_token(
            data={
                "sub": username,
                "id": user_id,
                "es_admin": role in {"admin", "super_admin"},
                "rol": role,
                "email": f"{username}@example.com",
            }
        )

    def test_super_admin_puede_crear_super_admin(self):
        suffix = uuid.uuid4().hex[:8]
        token = self._token(user_id=901, username=f"super_{suffix}", role="super_admin")
        headers = {"Authorization": f"Bearer {token}"}

        response = https_client.post(
            "/api/usuarios/",
            headers=headers,
            json={
                "username": f"nuevo_super_{suffix}",
                "email": f"nuevo_super_{suffix}@example.com",
                "password": "TestPassword123!",
                "nombre_completo": "Nuevo Super",
                "rol": "super_admin",
                "es_admin": True,
                "es_activo": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["rol"] == "super_admin"
        assert data["es_admin"] is True

    def test_admin_no_puede_crear_super_admin(self):
        suffix = uuid.uuid4().hex[:8]
        token = self._token(user_id=902, username=f"admin_{suffix}", role="admin")
        headers = {"Authorization": f"Bearer {token}"}

        response = https_client.post(
            "/api/usuarios/",
            headers=headers,
            json={
                "username": f"intento_super_{suffix}",
                "email": f"intento_super_{suffix}@example.com",
                "password": "TestPassword123!",
                "nombre_completo": "Intento Super",
                "rol": "super_admin",
                "es_admin": True,
                "es_activo": True,
            },
        )

        assert response.status_code == 403


class TestJwtRotation:
    """Tests para rotacion de llaves JWT."""

    def test_verify_token_acepta_llave_previa_en_rotacion(self, monkeypatch):
        previous_key = "previous-secret-key-for-rotation"
        current_key = "current-secret-key-for-rotation"

        token = jwt.encode(
            {
                "sub": "rot_user",
                "id": 999,
                "es_admin": False,
                "rol": "viewer",
            },
            previous_key,
            algorithm=security_module.ALGORITHM,
        )

        monkeypatch.setattr(security_module, "JWT_SIGNING_KEY", current_key)
        monkeypatch.setattr(security_module, "JWT_PREVIOUS_KEYS", [previous_key])

        payload = security_module.verify_token(token)
        assert payload["username"] == "rot_user"


class TestSecurityPhase2:
    """Tests de endurecimiento para Fase 2."""

    @staticmethod
    def _token(role: str) -> str:
        return create_access_token(
            data={
                "sub": f"role_{role}",
                "id": 1200 if role == "admin" else 1201,
                "es_admin": role in {"admin", "super_admin"},
                "rol": role,
                "email": f"{role}@example.com",
            }
        )

    def test_execute_query_select_requiere_admin(self):
        viewer_headers = {"Authorization": f"Bearer {self._token('viewer')}"}

        response = https_client.post(
            "/api/databases/database_manager/query",
            headers=viewer_headers,
            params={"query": "SELECT 1"},
        )

        assert response.status_code == 403

    def test_execute_query_select_admin_sin_bloqueo_por_rol(self):
        admin_headers = {"Authorization": f"Bearer {self._token('admin')}"}

        response = https_client.post(
            "/api/databases/database_manager/query",
            headers=admin_headers,
            params={"query": "SELECT 1"},
        )

        assert response.status_code != 403

    def test_backup_paths_requiere_admin(self):
        viewer_headers = {"Authorization": f"Bearer {self._token('viewer')}"}

        response = https_client.get("/api/export/backup/paths", headers=viewer_headers)

        assert response.status_code == 403

    def test_backup_paths_admin_permitido(self, monkeypatch):
        admin_headers = {"Authorization": f"Bearer {self._token('admin')}"}

        class _FakeBackupManager:
            def __init__(self, _db):
                pass

            def get_backup_paths(self):
                return [{"path": "C:/backups", "is_active": True}]

        monkeypatch.setattr(export_api, "BackupManager", _FakeBackupManager)

        response = https_client.get("/api/export/backup/paths", headers=admin_headers)

        assert response.status_code == 200
        assert response.json()["status"] == "success"

    def test_qr_verify_by_id_publico_bloqueado_sin_auth(self):
        response = client.get("/api/qr/public/verify-by-id/1")
        assert response.status_code in {401, 403}

    def test_qr_verify_by_id_admin_no_bloqueado_por_auth(self):
        admin_headers = {"Authorization": f"Bearer {self._token('admin')}"}
        response = https_client.get("/api/qr/public/verify-by-id/1", headers=admin_headers)
        assert response.status_code != 403


class TestSecurityPhase3:
    """Tests para hardening de fase 3."""

    def test_cors_preflight_no_usa_wildcard_methods(self):
        origin = (app_config.CORS_ORIGINS or ["http://localhost:3000"])[0]
        response = client.options(
            "/api/health",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
            },
        )

        assert response.status_code in {200, 204}
        allow_methods = response.headers.get("access-control-allow-methods", "")
        assert "*" not in allow_methods

    def test_api_debug_default_es_seguro(self):
        assert app_config.API_DEBUG is False

    def test_token_con_rol_escalado_se_normaliza_con_bd(self):
        db = TestingSessionLocal()
        repo = RepositorioUsuario(db)
        suffix = uuid.uuid4().hex[:8]
        usuario = repo.crear(
            UsuarioCrear(
                username=f"viewer_{suffix}",
                email=f"viewer_{suffix}@example.com",
                password="TestPassword123!",
                nombre_completo="Viewer Phase3",
                rol="viewer",
                es_admin=False,
            )
        )
        db.close()

        token_escalado = create_access_token(
            data={
                "sub": usuario.username,
                "id": usuario.id,
                "es_admin": True,
                "rol": "admin",
                "email": usuario.email,
            }
        )
        headers = {"Authorization": f"Bearer {token_escalado}"}

        response = https_client.post(
            "/api/databases/database_manager/query",
            headers=headers,
            params={"query": "SELECT 1"},
        )

        assert response.status_code == 403

    def test_usuario_inactivo_no_autoriza_token_vigente(self):
        db = TestingSessionLocal()
        repo = RepositorioUsuario(db)
        suffix = uuid.uuid4().hex[:8]
        usuario = repo.crear(
            UsuarioCrear(
                username=f"inactive_{suffix}",
                email=f"inactive_{suffix}@example.com",
                password="TestPassword123!",
                nombre_completo="Inactive Phase3",
                rol="viewer",
                es_admin=False,
                es_activo=False,
            )
        )
        db.close()

        token = create_access_token(
            data={
                "sub": usuario.username,
                "id": usuario.id,
                "es_admin": False,
                "rol": "viewer",
                "email": usuario.email,
            }
        )
        headers = {"Authorization": f"Bearer {token}"}

        response = https_client.get("/api/auth/me", headers=headers)
        assert response.status_code == 401


class TestAlertasRoles:
    """Tests para permisos de alertas y visibilidad de capacidades de rol."""

    @staticmethod
    def _token(role: str) -> str:
        return create_access_token(
            data={
                "sub": f"alerts_{role}",
                "id": 1700 if role == "admin" else 1701 if role == "super_admin" else 1702,
                "es_admin": role in {"admin", "super_admin"},
                "rol": role,
                "email": f"alerts_{role}@example.com",
            }
        )

    def test_admin_puede_enviar_alerta_sistema(self):
        headers = {"Authorization": f"Bearer {self._token('admin')}"}

        response = https_client.post(
            "/api/alertas/enviar-json",
            headers=headers,
            json={
                "titulo": "Mantenimiento programado",
                "mensaje": "Se realizará ventana de mantenimiento a las 23:00.",
                "nivel": "warning",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["titulo"] == "Mantenimiento programado"
        assert data["nivel"] == "warning"

    def test_viewer_no_puede_enviar_alerta_sistema(self):
        headers = {"Authorization": f"Bearer {self._token('viewer')}"}

        response = https_client.post(
            "/api/alertas/enviar-json",
            headers=headers,
            json={
                "titulo": "Intento sin permisos",
                "mensaje": "Este envío debe bloquearse.",
                "nivel": "info",
            },
        )

        assert response.status_code == 403

    def test_endpoint_capacidades_roles_retorna_cuatro_roles(self):
        headers = {"Authorization": f"Bearer {self._token('admin')}"}

        response = https_client.get("/api/usuarios/roles/capabilities", headers=headers)

        assert response.status_code == 200
        data = response.json()
        items = data.get("items", [])
        role_keys = {item.get("role") for item in items}
        assert {"viewer", "capture", "admin", "super_admin"}.issubset(role_keys)
