#!/bin/bash
# Script ROBUSTO para iniciar Database Manager con Docker
# Incluye detección de errores y soluciones automáticas
# Para Linux / macOS

set -o pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAX_RETRIES=3
WAIT_TIME=5
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

main() {
    clear
    echo ""
    echo "========================================"
    echo "Database Manager - Docker Auto Start"
    echo "========================================"
    echo ""
    
    echo "[PASO 1/5] Verificando Docker..."
    check_docker || handle_docker_error
    
    echo "[PASO 2/5] Verificando docker-compose..."
    check_compose || handle_compose_error
    
    echo "[PASO 3/5] Preparando ambiente..."
    cleanup_old_instances || true
    
    echo "[PASO 4/5] Iniciando servicios (puede tardar 2-3 minutos)..."
    start_services || handle_start_error
    
    echo "[PASO 5/5] Verificando servicios..."
    verify_services || handle_verify_error
    
    success
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        return 1
    fi
    echo "[OK] Docker instalado y disponible"
    return 0
}

check_compose() {
    if ! command -v docker-compose &> /dev/null; then
        return 1
    fi
    echo "[OK] docker-compose disponible"
    return 0
}

cleanup_old_instances() {
    docker-compose -f "$PROJECT_DIR/docker-compose.yml" down 2>/dev/null || true
    docker network prune -f 2>/dev/null || true
    echo "[OK] Ambiente preparado"
}

start_services() {
    cd "$PROJECT_DIR"
    
    for ((retry=1; retry<=MAX_RETRIES; retry++)); do
        echo "[REINTENTO $retry/$MAX_RETRIES] Iniciando docker-compose up..."
        
        if docker-compose up -d --build > docker_build.log 2>&1; then
            echo "[OK] Servicios iniciados"
            rm -f docker_build.log
            return 0
        fi
        
        echo "[ADVERTENCIA] docker-compose falló, analizando error..."
        
        if [ $retry -eq 1 ]; then
            echo "[ACCIÓN] Limpiando volúmenes huérfanos..."
            docker volume prune -f 2>/dev/null || true
        elif [ $retry -eq 2 ]; then
            echo "[ACCIÓN] Eliminando contenedores antiguos..."
            docker-compose down -v 2>/dev/null || true
            sleep $WAIT_TIME
        fi
    done
    
    echo -e "${RED}[ERROR] No se pueden iniciar servicios${NC}"
    cat docker_build.log
    rm -f docker_build.log
    return 1
}

verify_services() {
    local max_wait=60
    local waited=0
    
    while [ $waited -lt $max_wait ]; do
        clear
        echo ""
        echo "========================================"
        echo "Database Manager - Esperando servicios"
        echo "Tiempo de espera: $waited/$max_wait segundos"
        echo "========================================"
        echo ""
        
        docker-compose ps
        
        # Verificar que ambos servicios estén arriba
        if docker-compose ps | grep -q "database_manager_db" && \
           docker-compose ps | grep -q "database_manager_api"; then
            
            # Verificar healthcheck de MariaDB
            echo ""
            echo "[Verificando MariaDB...]"
            if docker-compose exec -T mariadb mariadb-admin ping -h localhost &>/dev/null; then
                echo "[OK] MariaDB está listo"
                return 0
            fi
        fi
        
        ((waited++))
        sleep 1
    done
    
    echo -e "${RED}[ERROR] Servicios no iniciaron en tiempo${NC}"
    return 1
}

success() {
    clear
    echo ""
    echo "========================================"
    echo "   [EXITO] Database Manager Running!"
    echo "========================================"
    echo ""
    echo "WEB:"
    echo "  URL:               http://localhost:8000"
    echo "  Swagger Docs:      http://localhost:8000/docs"
    echo "  ReDoc:             http://localhost:8000/redoc"
    echo ""
    echo "CREDENCIALES:"
    echo "  Usuario:           admin"
    echo "  Contraseña:        SecurePassword123!"
    echo ""
    echo "BASE DE DATOS:"
    echo "  Host:              localhost:3306"
    echo "  Usuario:           manager"
    echo "  Contraseña:        manager123"
    echo "  BD:                database_manager"
    echo ""
    echo "COMANDOS UTILES:"
    echo "  Ver logs:          docker-compose logs -f"
    echo "  Ver estado:        docker-compose ps"
    echo "  Detener:           docker-compose down"
    echo "  Limpiar todo:      docker-compose down -v"
    echo ""
    echo "Abre http://localhost:8000 en tu navegador"
    echo ""
}

handle_docker_error() {
    clear
    echo ""
    echo "========================================"
    echo "[ERROR CRITICO] Docker no encontrado"
    echo "========================================"
    echo ""
    echo "Soluciones:"
    echo "1. Descarga Docker Desktop:"
    echo "   https://www.docker.com/products/docker-desktop"
    echo ""
    echo "2. O instala Docker desde tu gestor de paquetes:"
    echo "   macOS (Homebrew):  brew install docker"
    echo "   Ubuntu/Debian:     sudo apt install docker.io docker-compose"
    echo "   Fedora:            sudo dnf install docker docker-compose"
    echo ""
    echo "3. Asegúrate de que Docker está ejecutándose"
    echo ""
    exit 1
}

handle_compose_error() {
    clear
    echo ""
    echo "========================================"
    echo "[ERROR] docker-compose no encontrado"
    echo "========================================"
    echo ""
    echo "Soluciones:"
    echo "1. Reinstala Docker Desktop (incluye docker-compose)"
    echo "2. O instala docker-compose manualmente:"
    echo "   https://docs.docker.com/compose/install/"
    echo ""
    exit 1
}

handle_start_error() {
    clear
    echo ""
    echo "========================================"
    echo "[ERROR] No se pudieron iniciar servicios"
    echo "========================================"
    echo ""
    echo "Soluciones automáticas intentadas:"
    echo "1. Se limpió volúmenes huérfanos"
    echo "2. Se eliminaron contenedores antiguos"
    echo ""
    echo "Pruebas manuales adicionales:"
    echo "1. Verifica que puertos 8000 y 3306 no estén en uso:"
    echo "   lsof -i :8000"
    echo "   lsof -i :3306"
    echo ""
    echo "2. Reinicia Docker completamente"
    echo ""
    echo "3. Reset completo:"
    echo "   docker-compose down -v"
    echo "   docker system prune -a -f"
    echo ""
    exit 1
}

handle_verify_error() {
    clear
    echo ""
    echo "========================================"
    echo "[ERROR] Servicios no iniciaron correctamente"
    echo "========================================"
    echo ""
    echo "Mira los logs:"
    echo "  docker-compose logs"
    echo ""
    echo "Comprueba estado:"
    echo "  docker-compose ps"
    echo ""
    exit 1
}

main "$@"

