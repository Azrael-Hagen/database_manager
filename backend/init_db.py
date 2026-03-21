"""Script mejorado de inicialización de base de datos."""

import logging
import sys
from app.database.orm import SessionLocal, init_db
from app.database.repositorios import RepositorioUsuario
from app.schemas import UsuarioCrear
from app.config import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_admin_user():
    """Crear usuario administrador."""
    db = SessionLocal()
    repo = RepositorioUsuario(db)
    
    # Verificar si el admin existe
    admin = repo.obtener_por_username("admin")
    
    if admin:
        logger.info("✓ Usuario admin ya existe")
        return admin
    
    # Crear admin
    try:
        admin_data = UsuarioCrear(
            username="admin",
            email="admin@example.com",
            password="Admin123!",
            nombre_completo="Administrador"
        )
        
        admin = repo.crear(admin_data)
        admin.es_admin = True
        db.add(admin)
        db.commit()
        
        logger.info("✓ Usuario admin creado exitosamente")
        logger.warning("⚠️ CAMBIAR CONTRASEÑA INMEDIATAMENTE: admin / Admin123!")
        return admin
    except Exception as e:
        logger.error(f"❌ Error creando admin: {e}")
        db.rollback()
        return None
    finally:
        db.close()


def main():
    """Función principal."""
    logger.info("=" * 60)
    logger.info("INICIALIZANDO DATABASE MANAGER")
    logger.info("=" * 60)
    
    try:
        # 1. Conectar a BD
        logger.info("[1/4] Conectando a base de datos...")
        logger.info(f"      Conectar a: {config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}")
        
        # 2. Crear tablas
        logger.info("[2/4] Creando tablas...")
        init_db()
        logger.info("      ✓ Tablas creadas/verificadas")
        
        # 3. Crear usuario admin
        logger.info("[3/4] Creando usuario administrador...")
        admin = create_admin_user()
        if not admin:
            logger.error("     ❌ No se pudo crear usuario admin")
            return 1
        
        # 4. Verificar permisos
        logger.info("[4/4] Verificando permisos...")
        db = SessionLocal()
        try:
            # Intentar leer de usuarios
            from app.models import Usuario
            count = db.query(Usuario).count()
            logger.info(f"      ✓ Permisos correctos ({count} usuarios)")
        except Exception as e:
            logger.error(f"      ❌ Error de permisos: {e}")
            return 1
        finally:
            db.close()
        
        logger.info("=" * 60)
        logger.info("✅ INICIALIZACIÓN COMPLETADA EXITOSAMENTE")
        logger.info("=" * 60)
        logger.info("")
        logger.info("PRÓXIMOS PASOS:")
        logger.info("1. Iniciir servidor: python main.py")
        logger.info("2. Acceder a http://localhost:8000/docs")
        logger.info("3. LOGIN con usuario: admin")
        logger.info("4. CAMBIAR CONTRASEÑA inmediatamente")
        logger.info("")
        
        return 0
    
    except Exception as e:
        logger.error(f"❌ ERROR CRÍTICO: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
