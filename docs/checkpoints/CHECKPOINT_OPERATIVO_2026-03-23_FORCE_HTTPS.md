# CHECKPOINT OPERATIVO 2026-03-23 - FORCE HTTPS

## Objetivo
Forzar acceso seguro: no permitir ingreso operativo por HTTP.

## Cambios
- Se añadió configuración de seguridad HTTPS:
  - `SSL_PORT`
  - `FORCE_HTTPS`
- Se implementó middleware global en backend para:
  - aceptar tráfico HTTPS,
  - redirigir HTTP a HTTPS cuando TLS está configurado,
  - bloquear HTTP con `426 Upgrade Required` cuando no existe TLS,
  - conservar `GET /api/health` por HTTP para healthchecks internos.

## Archivos modificados
- `backend/main.py`
- `backend/app/config.py`
- `.env.example`
- `README.md`

## Validación
- Import/sanidad backend OK.
- Sin errores de análisis en archivos modificados.

## Notas operativas
- Para activar comportamiento en ejecución, reiniciar el backend.
- Si usas reverse proxy TLS, conservar encabezados `X-Forwarded-Proto`/`X-Forwarded-Host`.
