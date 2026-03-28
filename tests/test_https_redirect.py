"""Tests de redirección HTTPS para hosts LAN y localhost."""

from fastapi.testclient import TestClient

from main import app


def test_http_lan_host_redirects_to_https_default_port():
    client = TestClient(app, base_url="http://phantom.database.net")

    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "https://phantom.database.net/"


def test_http_explicit_dev_port_redirects_to_configured_ssl_port():
    client = TestClient(app, base_url="http://example.com:8000")

    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "https://example.com:8443/"


def test_http_private_lan_ip_does_not_redirect():
    client = TestClient(app, base_url="http://192.168.1.162")

    response = client.get("/api/health", follow_redirects=False)

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_http_domain_login_redirects_to_https_same_host_without_dev_port():
    client = TestClient(app, base_url="http://phantom.database.net")

    response = client.post(
        "/api/auth/login",
        json={"username": "invalid", "password": "invalid"},
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert response.headers["location"] == "https://phantom.database.net/api/auth/login"


def test_http_domain_mobile_route_redirects_to_https_same_host_without_dev_port():
    client = TestClient(app, base_url="http://phantom.database.net")

    response = client.get("/m", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "https://phantom.database.net/m"


def test_http_private_ip_login_does_not_redirect_and_returns_auth_status():
    client = TestClient(app, base_url="http://192.168.1.162")

    response = client.post(
        "/api/auth/login",
        json={"username": "invalid", "password": "invalid"},
        follow_redirects=False,
    )

    # Sin redirección HTTPS para IP LAN; el endpoint responde autenticación directa.
    assert response.status_code == 401
