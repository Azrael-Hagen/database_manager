#!/bin/bash
# Script de deployment para Database Manager - PRODUCCIÓN

set -e

echo "=========================================="
echo "Database Manager - Deployment Script"
echo "=========================================="

# Variables
ENVIRONMENT=${1:-production}
BRANCH=${2:-main}

echo "[1] Obteniendo configuración..."

# Crear .env si no existe
if [ ! -f .env ]; then
    echo "Creando archivo .env..."
    cp .env.example .env
    echo "⚠️ IMPORTANTE: Edita .env con tus configuraciones antes de continuar"
    read -p "Presiona Enter cuando hayas editado .env..."
fi

echo "[2] Validando Docker..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker no está instalado"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose no está instalado"
    exit 1
fi

echo "✓ Docker disponible"

echo "[3] Construyendo images..."
docker-compose build --no-cache

echo "[4] Iniciando servicios..."
docker-compose up -d

echo "[5] Esperando a que BD esté lista..."
sleep 10

echo "[6] Ejecutando migraciones..."
docker-compose exec -T backend python init_db.py

echo "[7] Creando usuario admin..."
docker-compose exec -T backend python -c "
from app.database.orm import SessionLocal, init_db
from app.database.repositorios import RepositorioUsuario
from app.schemas import UsuarioCrear
from app.models import Usuario

db = SessionLocal()
repo = RepositorioUsuario(db)

# Verificar si admin existe
if not repo.obtener_por_username('admin'):
    admin = repo.crear(UsuarioCrear(
        username='admin',
        email='admin@database-manager.local',
        password='SecurePassword123!',
        nombre_completo='Administrador'
    ))
    # Actualizar a admin
    admin.es_admin = True
    db.add(admin)
    db.commit()
    print('✓ Usuario admin creado')
else:
    print('✓ Usuario admin ya existe')

db.close()
"

echo "[8] Verificando salud..."
sleep 5

HEALTH=$(curl -s http://localhost:8000/api/health || echo "failed")
if echo $HEALTH | grep -q "ok"; then
    echo "✓ Backend operacional"
else
    echo "❌ Backend no responde. Revisa los logs:"
    docker-compose logs backend
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ DEPLOYMENT COMPLETADO"
echo "=========================================="
echo ""
echo "📊 URLs disponibles:"
echo "  • API: http://localhost:8000/api"
echo "  • Documentación: http://localhost:8000/docs"
echo "  • Panel Web: http://localhost"
echo ""
echo "📝 Credenciales de Admin:"
echo "  • Usuario: admin"
echo "  • Contraseña: SecurePassword123!"
echo ""
echo "⚠️ CAMBIAR CONTRASEÑA INMEDIATAMENTE EN PRODUCCIÓN"
echo ""
echo "Comando para ver logs:"
echo "  docker-compose logs -f backend"
echo ""
echo "Comando para detener servicios:"
echo "  docker-compose down"
echo ""
