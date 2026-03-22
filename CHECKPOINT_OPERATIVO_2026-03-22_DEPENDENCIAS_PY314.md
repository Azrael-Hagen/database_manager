# Checkpoint Operativo Dependencias Python 3.14 (2026-03-22)

## Objetivo del bloque
- Adoptar la opcion A: normalizar dependencias del backend para ejecucion local en Python 3.14.

## Contexto tecnico confirmado
- El entorno local del backend (`backend/venv`) corre sobre Python 3.14.3.
- Se detectaron incompatibilidades en pins actuales:
  - `SQLAlchemy==2.0.23` falla en import con Python 3.14.
  - `PyJWT==2.8.1` no existe en PyPI.
  - `Pillow==10.1.0` falla de build en Python 3.14.

## Criterio de aceptacion del bloque
1. `pip install -r backend/requirements.txt` completa sin errores en Python 3.14.
2. `backend/verify_system.py` ejecuta y pasa validaciones.
3. No se alteran flujos funcionales de negocio (solo compatibilidad de entorno).
