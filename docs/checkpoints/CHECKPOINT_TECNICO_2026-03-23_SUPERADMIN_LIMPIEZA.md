# CHECKPOINT TECNICO - 2026-03-23

## Alcance
- Validar flujo de permisos para creacion de usuarios super_admin.
- Limpiar archivos temporales/corruptos generados durante diagnostico.

## Cambios aplicados
1. Schemas actualizados para aceptar rol `super_admin` en create/update/response.
2. Repositorio de usuarios ajustado para que `es_admin=True` cuando el rol es `admin` o `super_admin`.
3. Endpoint de creacion/actualizacion de usuarios:
   - Solo `super_admin` puede crear o asignar rol `super_admin`.
4. Test nuevo agregado para validar:
   - `super_admin` SI puede crear `super_admin`.
   - `admin` NO puede crear `super_admin`.
5. Limpieza de archivos no productivos:
   - scripts/temp_promote.py
   - scripts/promote_to_super_admin.py (corrupto)
   - query_usuarios.py
   - query_usuarios_mariadb.py
   - query_usuarios_sqlalchemy.py

## Riesgos controlados
- Se mantiene compatibilidad del flujo existente de login/token.
- Se evita escalamiento de privilegios accidental desde rol `admin`.

## Siguiente verificacion
- Ejecutar pytest focalizado sobre `tests/test_api.py`.
