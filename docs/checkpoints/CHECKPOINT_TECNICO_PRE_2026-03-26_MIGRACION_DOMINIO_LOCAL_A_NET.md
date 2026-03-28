# CHECKPOINT TÉCNICO PREVIO — 2026-03-26 — Migración dominio .local a .net

## Objetivo
Migrar hostname operativo de `phantom.database.local` a `phantom.database.net` y validar funcionamiento E2E (resolución + acceso app).

## Alcance autorizado
- Scripts de setup de host/TLS
- Configuración de entorno del backend (`.env`/`CORS`)
- Configuración Nginx local
- Arranque rápido en Windows (`start.bat`)
- Compatibilidad de descubrimiento en app cliente

## Riesgos identificados
1. `NXDOMAIN` si `hosts` no se actualiza o se mantiene hostname antiguo.
2. Bloqueo CORS si no se agregan orígenes `http/https` del nuevo dominio.
3. Redirecciones HTTPS inválidas si el certificado no incluye el nuevo CN/SAN.
4. Regresión en clientes móviles si descubrimiento sigue apuntando a `.local`.

## Criterios de aceptación
- [x] `Resolve-DnsName phantom.database.net` retorna IP local esperada (`192.168.1.162`).
- [x] `GET http://phantom.database.net` responde desde backend local (redirige a HTTPS por política).
- [x] `GET https://phantom.database.net` responde con validación TLS estricta correcta.
- [x] `/api/health` responde `status=ok` vía hostname nuevo (`http` y `https` con omisión de validación).
- [x] CORS permite `http://phantom.database.net` y `https://phantom.database.net` (actualizado en `.env`).

## Evidencia E2E
- `LOCAL_HEALTH:ok` por `http://127.0.0.1:8000/api/health`
- `DNS_NET_IP:192.168.1.162`
- `NET_HEALTH:{"status":"ok", ...}` por `http://phantom.database.net/api/health`
- `HTTPS_HEALTH_STRICT:{"status":"ok", ...}` por `https://phantom.database.net/api/health`

## Rollback
- Restaurar hostname anterior en `.env`, scripts de setup y `nginx.local.conf`.
- Reejecutar setup de host/TLS para `.local`.

## Estado
COMPLETADO
