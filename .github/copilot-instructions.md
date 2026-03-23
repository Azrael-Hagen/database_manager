# Instrucciones Obligatorias del Proyecto

Estas reglas son obligatorias para cualquier cambio en este workspace.

1. Usar las instrucciones del usuario como pivote de implementación.
2. No modificar funcionalidades ya validadas sin autorización explícita.
3. Mantener sincronización estricta UI y base de datos:
- No mostrar datos que no existan realmente en la BD.
- Cualquier listado debe provenir de consulta actual al backend/BD.
4. En la sección Datos, la base predeterminada debe ser `database_manager`.
5. El campo Empresa no forma parte del flujo operativo de agentes y no debe mostrarse en formularios/tablas de gestión.
6. Antes de cambios significativos, generar checkpoint técnico.
7. Las pruebas de diagnóstico deben ser temporales y orientadas a logs; no dejar scripts de prueba permanentes salvo solicitud expresa.
8. Verificar funcionamiento end-to-end tras cada bloque de cambios.
