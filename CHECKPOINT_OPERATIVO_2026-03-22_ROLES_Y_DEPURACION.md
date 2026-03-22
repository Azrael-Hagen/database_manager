# Checkpoint Operativo Roles y Depuracion (2026-03-22)

## Objetivo del bloque
- Implementar 3 roles de usuario: visor, capturista y administrador.
- Permitir eliminacion definitiva de registros y usuarios bajo control de permisos.
- Agregar ordenamiento configurable por el usuario en listados clave.
- Incorporar herramientas seguras de depuracion de tablas y creacion de vistas utiles.

## Estado confirmado antes del cambio
- El sistema actual solo distingue `es_admin` contra no-admin.
- Existen 12 tablas base en `database_manager` y actualmente no hay vistas activas en esa BD.
- La UI de usuarios tambien depende de `es_admin` y no tiene borrado definitivo.
- El endpoint `/api/datos` recibe `ordenar_por` y `direccion`, pero el repositorio hoy no aplica ese orden realmente.

## Criterio de seguridad para este bloque
- No se borraran tablas operativas existentes automaticamente.
- La depuracion automatica se limitara a objetos temporales/test claramente identificables.
- Las operaciones destructivas quedaran restringidas a administradores y requeriran invocacion explicita.