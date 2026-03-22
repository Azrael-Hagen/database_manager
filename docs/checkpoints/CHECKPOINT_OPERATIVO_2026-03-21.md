# Checkpoint Operativo (2026-03-21)

> Estado histórico. El checkpoint vigente es `CHECKPOINT_OPERATIVO_2026-03-21_BLOQUE2.md`.

## Objetivo
Consolidar estado funcional sin romper avances previos.

## Reglas de trabajo aplicadas
- Mantener funcionalidades existentes validadas.
- No introducir cambios de comportamiento no solicitados.
- Ejecutar verificación técnica tras cada ajuste.
- Priorizar consistencia entre UI y datos persistidos.

## Estado técnico confirmado
- Tabla de agentes: `datos_importados`.
- Registros presentes en BD: disponibles y consultables por API.
- Flujo de QR: creación y consulta implementadas.
- Frontend: base de datos predeterminada configurada en el código actual (`database_manager`).

## Riesgos abiertos
- Hay scripts de diagnóstico/prueba creados durante depuración que no forman parte del runtime.
- Existe cambio de branding/logo pendiente en estado git.

## Criterio de aceptación desde este checkpoint
1. UI solo muestra datos realmente persistidos en la BD.
2. Consulta de agentes retorna filas reales y no placeholders.
3. Funciones de QR operan sobre agentes existentes.
4. Se conserva comportamiento ya probado.

## Pruebas a ejecutar desde este checkpoint
- Ejecutar pruebas temporales de logs sin dejar scripts permanentes.

## Nota
Si el usuario define otra BD como predeterminada, se cambiará únicamente ese valor, sin alterar el resto del flujo.
