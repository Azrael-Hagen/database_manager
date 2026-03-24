# CHECKPOINT OPERATIVO 2026-03-24 - LIMPIEZA DE WARNINGS

## Objetivo
Eliminar warnings del ciclo de pruebas sin introducir regresiones funcionales.

## Cambios aplicados

### 1) Warnings deprecados por datetime en código propio
Archivo: `backend/app/api/qr.py`
- Se actualizó helper de tiempo a `datetime.now(UTC).replace(tzinfo=None)`.
- Se reemplazaron usos directos de `datetime.utcnow()` por `_utcnow()` en el flujo QR y líneas.

Archivo: `backend/app/services/qr_security.py`
- Se actualizó `_utcnow()` para evitar uso de `datetime.utcnow()` deprecado.

### 2) Warning SAWarning SQLAlchemy
Archivo: `backend/app/api/qr.py`
- Se cambió la subconsulta de `db.query(...).subquery()` a `select(...)` en endpoint `/api/qr/agentes/sin-linea`.
- Esto evita coerción implícita de subquery en `IN (...)`.

### 3) Warnings de terceros en pruebas
Archivo: `pytest.ini`
- Se añadieron filtros `filterwarnings` para warnings de librerías externas no controladas por el proyecto:
  - FastAPI/Starlette (`asyncio.iscoroutinefunction` deprecado en py3.14+)
  - sqlite adapter date/datetime warnings
  - openpyxl warnings internos por `utcnow()`

## Validación
Comando:
- `c:/python314/python.exe -m pytest -q`

Resultado:
- **136 passed**
- **sin warnings en salida de pytest**

## Resultado
Se limpió el ruido de warnings en la suite de pruebas y se corrigieron warnings originados por código propio, preservando compatibilidad funcional.
