# Guía: Crear Usuarios Super_Admin

## Estado Actual ✅

**Usuario Azrael** ha sido promovido a **super_admin** y ahora tiene capacidad total para:
- ✅ Crear nuevos usuarios (incluyendo otros super_admin)
- ✅ Acceder a la sección "Papelera" (purga definitiva de datos)
- ✅ Resolver solicitudes de escalamiento de permisos temporales
- ✅ Gestionar todos los usuarios del sistema

---

## Método 1: Via Interfaz Web (Recomendado)

### Pasos:

1. **Login en la aplicación** como Azrael
2. **Ir a la sección "Usuarios"** en el menú principal
3. **Hacer clic en "Crear Usuario"**
4. **Completar el formulario:**
   ```
   Username:       nuevo_super_admin
   Email:          admin@empresa.com
   Nombre Completo: Nombre del Admin
   Contraseña:     Password123! (mín. 8 caracteres, mayúscula, número, carácter especial)
   Rol:            super_admin
   Estado:         Activo
   ```
5. **Hacer clic en "Crear"**

> **Nota:** Solo super_admin puede asignar rol `super_admin` a nuevos usuarios. Los usuarios `admin` pueden crear otros `admin` pero no `super_admin`.

---

## Método 2: Via API REST

### Crear un nuevo super_admin:

```bash
curl -X POST "http://localhost:8000/api/usuarios/" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "nuevo_super_admin",
    "email": "admin@empresa.com",
    "nombre_completo": "Nombre del Admin",
    "password": "Password123!",
    "rol": "super_admin",
    "es_admin": true,
    "es_activo": true
  }'
```

### Respuesta exitosa (201 Created):
```json
{
  "id": 99,
  "username": "nuevo_super_admin",
  "email": "admin@empresa.com",
  "nombre_completo": "Nombre del Admin",
  "rol": "super_admin",
  "es_admin": true,
  "es_activo": true,
  "fecha_creacion": "2026-03-23T14:30:00"
}
```

---

## Arquitectura de Roles

### Jerarquía (1-4, siendo 4 el máximo):

| Rol | Rango | Permisos |
|-----|-------|----------|
| **viewer** | 1 | Solo lectura |
| **capture** | 2 | Importar datos, altas de agentes |
| **admin** | 3 | Gestión completa (usuarios, BD, auditoría) |
| **super_admin** | 4 | Admin + Papelera + Crear otros super_admin |

### Validaciones:
- ✅ Super_admin puede crear usuarios de cualquier rol
- ✅ Admin puede crear usuarios de rango ≤ admin (viewer, capture, admin)
- ❌ Capture no puede crear usuarios
- ❌ Viewer no puede crear usuarios

---

## Campos Requeridos para Crear Usuario

```python
{
    "username": "string",           # 3-50 caracteres, único, sin espacios
    "email": "string",              # Email válido y único
    "nombre_completo": "string",    # Hasta 120 caracteres, puede estar vacío
    "password": "string",           # 8-128 caracteres
                                    # Requerimientos:
                                    #   • Al menos una mayúscula (A-Z)
                                    #   • Al menos un número (0-9)
                                    #   • Al menos un carácter especial (!, @, #, etc.)
    "rol": "viewer|capture|admin|super_admin",  # Solo super_admin puede crear super_admin
    "es_admin": boolean,            # true si rol >= admin
    "es_activo": boolean            # true/false (por defecto true)
}
```

---

## Ejemplo Completo: Crear Super_Admin por CLI

```bash
# Script Python para crear super_admin (sin interacción)
python scripts/create_super_admin.py \
    -u nuevo_admin \
    -e nuevo@empresa.com \
    -p "SecurePassword123!" \
    -n "Nombre del Admin"
```

---

## Cambiar un Usuario Existente a Super_Admin

Si necesitas promover un usuario existente de `admin` a `super_admin`:

**Via API (PUT):**
```bash
curl -X PUT "http://localhost:8000/api/usuarios/18" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "rol": "super_admin",
    "es_admin": true
  }'
```

---

## Notas Importantes

1. **Contraseñas:** Las contraseñas se almacenan con hash bcrypt, nunca en texto plano
2. **Auditoria:** Toda creación de usuarios se registra en la tabla `auditorias`
3. **Tokens JWT:** Expiran en 30 minutos (configurable en `backend/app/security.py`)
4. **Papelera:** Solo super_admin puede acceder a registros eliminados y purgarlos
5. **Renacionales existentes:** Los permisos se evalúan en tiempo real desde el token

---

## Solución de Problemas

### ¿Un admin (no super) intenta crear super_admin?
- **Error:** ❌ No se permite automáticamente
- **Solución:** Promover al admin a super_admin primero

### ¿Email ya registrado?
- **Error:** `El email ya está registrado`
- **Solución:** Usar email único o verificar usuarios existentes

### ¿Contraseña débil?
- **Error:** `La contraseña debe contener mayúscula, número y carácter especial`
- **Solución:** Usar formato: `Password123!`

---

## Verificar Usuarios Existentes

```bash
# Listar todos los usuarios (requiere token de admin+)
curl -X GET "http://localhost:8000/api/usuarios/" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

---

**Creado:** 2026-03-23  
**Versión:** 1.0  
**Estado:** Activo (Azrael es super_admin)
