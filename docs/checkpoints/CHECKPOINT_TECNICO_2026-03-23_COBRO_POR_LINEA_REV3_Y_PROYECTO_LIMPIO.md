# CHECKPOINT TECNICO - 2026-03-23 (Cobro por linea rev3 y proyecto limpio)

## Objetivo
Cerrar la implementacion de cobro por linea de forma end-to-end, validar entorno limpio y publicar revision de version.

## Cambios aplicados
1. Cobro por linea en UI/flujo operativo
- Altas y asignaciones: se solicita configuracion de primer cobro cuando es la primera linea del agente.
- Opciones soportadas en primer cobro: semana de inicio y/o cargo inicial.
- Filtro de lineas en Altas: todas/libres/ocupadas.

2. Estado de Agentes consolidado
- Una fila por agente.
- Muestra conteo de lineas activas y numeros agregados.
- Mantiene QR unico por agente aun con multiples lineas.

3. Verificacion QR y resumenes
- Se muestran campos de tarifa por linea, lineas activas y cargo semanal total.
- Se mantiene saldo acumulado y semanas pendientes en el resumen de cobranza.

4. Correccion tecnica durante validacion
- Se corrige import faltante de `Numeric` en modelos SQLAlchemy para evitar fallo de coleccion en tests.

## Limpieza y validacion
- Dependencias instaladas desde `backend/requirements.txt`.
- Suite ejecutada con Python 3.14 configurado:
  - Resultado: 44 passed.

## Versionado
- Se actualiza `deploy/version-info.json` a `1.5.0-rev3`.
- Se agrega entrada `1.5.0-rev3` en `deploy/CHANGELOG.server.md`.
