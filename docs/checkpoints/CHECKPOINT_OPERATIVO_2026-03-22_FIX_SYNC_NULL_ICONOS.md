# CHECKPOINT OPERATIVO 2026-03-22 - FIX SYNC NULL + ICONOS UI

## Objetivo
Corregir error 500 en altas por sincronizacion legacy (`registro_agentes.agentes`) y mejorar UI con iconografia nueva.

## Hallazgo tecnico
- La tabla legacy `registro_agentes.agentes` tiene columnas no null (`Ubicacion`, `FP`, `FC`, `Grupo`).
- El backend enviaba `NULL` cuando esos datos no venian en payload.
- Resultado: `IntegrityError 1048: Column 'Ubicacion' cannot be null`.

## Accion aplicada
- Se normalizan campos legacy con fallback a string vacio y truncado seguro por longitud de columna.
- Fix aplicado en:
  - `backend/app/api/datos.py`
  - `backend/app/api/qr.py`

## Riesgo
- Bajo: solo afecta serializacion de sync legacy hacia columnas antiguas.

## Verificacion esperada
- `POST /api/datos/` deja de responder 500 por sync legacy.
- `POST /api/qr/agentes/manual` deja de responder 500 por sync legacy.
