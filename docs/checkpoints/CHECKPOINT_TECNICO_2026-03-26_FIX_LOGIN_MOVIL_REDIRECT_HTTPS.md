# CHECKPOINT TECNICO — 2026-03-26 — Fix Login Movil Redirect HTTPS

## Incidencia
No se podia iniciar sesion desde movil en dominio phantom.database.net.

## Causa raiz
La redireccion HTTP->HTTPS forzaba puerto :8443 en hosts LAN sin puerto explicito.
En clientes moviles, el flujo de login por HTTP intentaba POST a /api/auth/login y recibia 307 hacia https://phantom.database.net:8443/api/auth/login.
Ese puerto no es el endpoint publico esperado (debe ser 443), lo que rompe el flujo en ciertos clientes/redes.

## Cambios aplicados
- backend/main.py
  - Ajuste de _build_https_redirect_url:
    - Host LAN sin puerto explicito o :80 -> redireccion a https://host (443)
    - Host con puerto explicito de desarrollo (ej. :8000) -> redireccion a SSL_PORT (ej. :8443)
- tests/test_https_redirect.py (nuevo)
  - test_http_lan_host_redirects_to_https_default_port
  - test_http_explicit_dev_port_redirects_to_configured_ssl_port

## Validacion
- Pruebas automatizadas:
  - 2/2 passing en tests/test_https_redirect.py
- E2E operativo:
  - http://phantom.database.net/api/auth/login -> 307
  - Location: https://phantom.database.net/api/auth/login (sin :8443)
  - https://phantom.database.net/api/health -> status ok
  - http://127.0.0.1:8000/api/health -> status ok

## Estado
COMPLETADO
