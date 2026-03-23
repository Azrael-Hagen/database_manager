"""Tests de seguridad y autenticación."""

import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database.orm import Base, get_db
from app.models import Usuario
from app.schemas import UsuarioCrear
from app.security import create_access_token
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


class TestDatos:
    """Tests de endpoints de datos."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup antes de cada test."""
        usuario_data = {
            "username": "testuser_datos",
            "email": "testdatos@example.com",
            "password": "TestPassword123!",
            "nombre_completo": "Test Datos",
            "rol": "capture"
        }

        # Registrar (puede fallar si ya existe, lo ignoramos)
        https_client.post("/api/auth/registrar", json=usuario_data)

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
