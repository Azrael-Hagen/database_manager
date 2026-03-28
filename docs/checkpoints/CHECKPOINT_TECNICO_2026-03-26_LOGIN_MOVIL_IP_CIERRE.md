# CHECKPOINT TECNICO — 2026-03-26 — Login movil por IP (cierre)

## Sintoma reportado
Desde navegador movil en `http://192.168.1.162` no permitia iniciar sesion y quedaba en pantalla de login.

## Hallazgos
1. Redirección HTTPS en host IP privada:
- El middleware forzaba HTTP->HTTPS tambien para IP LAN.
- En movil, HTTPS por IP puede fallar por certificado no emitido para IP literal.

2. Usuario admin inactivo:
- En BD, `admin` existia con `es_activo = False`.
- Cualquier intento de login con admin devolvia 401.

## Correcciones aplicadas
1. Codigo backend:
- `backend/main.py`
- Regla de middleware HTTPS ajustada:
  - Se permite HTTP para host loopback/IP privada LAN.
  - Se conserva redireccion HTTPS para dominios/hosts no privados.

2. Pruebas automatizadas:
- `tests/test_https_redirect.py`
- Casos verdes:
  - redireccion LAN host -> 443
  - redireccion host con puerto explicito dev -> SSL_PORT
  - IP privada LAN no redirige y responde health 200

3. Estado de cuenta admin:
- Reactivado `admin` (`es_activo=True`) y password restablecido a `Admin123!` para recuperar acceso inmediato.

## Validacion E2E
- `POST http://192.168.1.162/api/auth/login` -> OK (token bearer)
- `GET http://192.168.1.162/api/auth/me` con token -> OK (`user=admin`, `es_activo=True`)
- Tests: `3 passed` en `tests/test_https_redirect.py`

## Estado
COMPLETADO
