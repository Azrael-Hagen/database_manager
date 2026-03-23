#!/usr/bin/env python
"""
Script para crear un usuario súper_admin con credenciales temporales.
USO: python scripts/create_super_admin.py -u admin_user -e admin@example.com -p TempPassword123!
     python scripts/create_super_admin.py   (sin argumentos pide interactivamente)
"""

import sys
import getpass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from sqlalchemy.exc import IntegrityError
from app.database.orm import SessionLocal
from app.models import Usuario
from app.security import hash_password, normalize_role
from datetime import datetime, timezone
import argparse

def create_super_admin(username=None, email=None, password=None, nombre_completo=None):
    """Crea un usuario súper_admin en la base de datos."""
    db = SessionLocal()
    try:
        if not username:
            username = input("Username para súper_admin: ").strip()
        if not email:
            email = input("Email: ").strip()
        if not password:
            password = getpass.getpass("Contraseña temporal (mínimo 12 caracteres): ")
            confirm = getpass.getpass("Confirma contraseña: ")
            if password != confirm:
                print("❌ Las contraseñas no coinciden.")
                return {"status": "error", "message": "Contraseñas no coinciden"}
        if not nombre_completo:
            nombre_completo = input("Nombre completo (opcional): ").strip() or "Administrador Principal"
        
        # Validaciones
        if len(username) < 3:
            print("❌ Username debe tener al menos 3 caracteres.")
            return {"status": "error", "message": "Username muy corto"}
        if len(password) < 12:
            print("❌ Contraseña debe tener al menos 12 caracteres.")
            return {"status": "error", "message": "Contraseña débil"}
        if "@" not in email:
            print("❌ Email inválido.")
            return {"status": "error", "message": "Email inválido"}
        
        # Verificar si el usuario ya existe
        existing = db.query(Usuario).filter(
            (Usuario.username == username) | (Usuario.email == email)
        ).first()
        if existing:
            print(f"❌ Usuario '{username}' o email '{email}' ya existe.")
            return {"status": "error", "message": "Usuario ya existe"}
        
        # Crear usuario
        new_user = Usuario(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            nombre_completo=nombre_completo,
            es_admin=True,
            rol="super_admin",
            es_activo=True,
            fecha_creacion=datetime.now(timezone.utc),
        )
        db.add(new_user)
        db.commit()
        
        print("\n✓ Súper_admin creado exitosamente:")
        print(f"  Username: {username}")
        print(f"  Email: {email}")
        print(f"  Nombre: {nombre_completo}")
        print(f"  Rol: super_admin")
        print(f"\n⚠️  IMPORTANTE:")
        print(f"  • Guarda estas credenciales en un lugar seguro.")
        print(f"  • El acceso a enviar alertas está restringido a la máquina servidor.")
        print(f"  • Puedes cambiar la contraseña en la sección Usuarios después de login.")
        
        return {
            "status": "ok",
            "user_id": new_user.id,
            "username": username,
            "email": email
        }
    
    except IntegrityError:
        db.rollback()
        print("❌ Error de integridad: el usuario o email ya existe.")
        return {"status": "error", "message": "Usuario ya existe"}
    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Crea un usuario súper_admin para la aplicación"
    )
    parser.add_argument("-u", "--username", help="Username")
    parser.add_argument("-e", "--email", help="Email")
    parser.add_argument("-p", "--password", help="Contraseña temporal (usar con cuidado)")
    parser.add_argument("-n", "--nombre", dest="nombre_completo", help="Nombre completo")
    args = parser.parse_args()
    
    result = create_super_admin(
        username=args.username,
        email=args.email,
        password=args.password,
        nombre_completo=args.nombre_completo
    )
    sys.exit(0 if result["status"] == "ok" else 1)
