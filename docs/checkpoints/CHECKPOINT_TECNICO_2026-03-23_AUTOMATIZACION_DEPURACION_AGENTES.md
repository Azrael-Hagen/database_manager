# CHECKPOINT TECNICO - 2026-03-23 (Automatizacion depuracion de agentes)

## Objetivo
Automatizar la depuracion de datos redundantes de agentes para mantener operacion limpia sin afectar registros con trazabilidad operativa.

## Cambios aplicados
1. Utilidad reutilizable de depuracion segura de agentes:
- `cleanup_redundant_agents` identifica y elimina:
  - registros test-like activos
  - duplicados exactos por firma operativa
- Nunca elimina registros con referencias en asignaciones/pagos/recibos.

2. Arranque del servidor:
- Se agrego tarea de depuracion al inicio de la API.
- Se controla por variable `AUTO_AGENT_DATA_CLEANUP_ON_STARTUP`.

3. Endpoint administrativo:
- Nuevo endpoint para depuracion manual con `dry_run`.
- Restringido a `database_manager`, rol admin y maquina servidor.

4. UI de mantenimiento:
- Nuevo boton "Depurar Agentes Redundantes".
- Flujo en dos pasos: analisis (dry run) y confirmacion de ejecucion.

## Riesgo controlado
- No se tocan tablas de historial operativo ni registros con dependencias.
- Sincroniza limpieza contra `registro_agentes.agentes` por ID cuando aplica.

## Verificacion
- Suite de pruebas ejecutada: 44 passed.
