"""Tests de seguridad y autenticación."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.orm import Base, get_db
from app.models import Usuario
from app.schemas import UsuarioCrear
from main import app

# DB de test en memoria
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
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
        # Crear usuario y token
        usuario_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "TestPassword123!",
            "nombre_completo": "Test"
        }
        
        # Registrar
        response = client.post("/api/auth/registrar", json=usuario_data)
        assert response.status_code == 200
        
        # Login
        login_response = client.post(
            "/api/auth/login",
            json={"username": "testuser", "password": "TestPassword123!"}
        )
        assert login_response.status_code == 200
        self.token = login_response.json()["access_token"]
    
    def test_listar_datos(self):
        """Test listar datos."""
        headers = {"Authorization": f"Bearer {self.token}"}
        response = client.get("/api/datos/", headers=headers)
        assert response.status_code == 200
        assert response.json()["status"] == "success"
    
    def test_crear_dato(self):
        """Test crear dato."""
        headers = {"Authorization": f"Bearer {self.token}"}
        response = client.post(
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
