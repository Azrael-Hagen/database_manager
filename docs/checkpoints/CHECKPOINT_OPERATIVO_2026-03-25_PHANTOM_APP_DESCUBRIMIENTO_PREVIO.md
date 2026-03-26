# Checkpoint Técnico — Phantom App Descubrimiento LAN

Fecha: 2026-03-25
Estado: En progreso

## Problema
- La APK no encuentra el servidor en algunos entornos LAN aun cuando el backend está activo.

## Hallazgos
- El barrido de IP solo revisa vecinos cercanos al móvil (`±12`), insuficiente cuando el servidor está lejos en el mismo `/24`.
- El descubrimiento solo prueba `http://*:8000`, pero el proyecto también puede exponerse por `http://*:80`.
- La IP local del Android se intenta obtener solo desde `WifiManager.connectionInfo`, un camino frágil y deprecado.

## Corrección prevista
- Barrido priorizado: vecinos cercanos + rango bajo de infraestructura (`.2` a `.40`).
- Probar puertos 80 y 8000.
- Fallback a `NetworkInterface` para obtener IPv4 privada del dispositivo.