#!/bin/bash
# Script de validación/testing para Database Manager

echo "=========================================="
echo "Database Manager - Test Suite"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS_COUNT=0
FAIL_COUNT=0

# Test 1: Python
echo -e "${YELLOW}[TEST 1]${NC} Verificando Python..."
if command -v python &> /dev/null; then
    PYTHON_VERSION=$(python --version 2>&1)
    echo -e "${GREEN}✓${NC} $PYTHON_VERSION"
    ((PASS_COUNT++))
else
    echo -e "${RED}✗${NC} Python no encontrado"
    ((FAIL_COUNT++))
fi

# Test 2: venv
echo ""
echo -e "${YELLOW}[TEST 2]${NC} Verificando entorno virtual..."
if [ -d "backend/venv" ]; then
    echo -e "${GREEN}✓${NC} Entorno virtual existe"
    ((PASS_COUNT++))
else
    echo -e "${RED}✗${NC} Entorno virtual no existe"
    echo "  Ejecuta: python -m venv backend/venv"
    ((FAIL_COUNT++))
fi

# Test 3: Dependencias
echo ""
echo -e "${YELLOW}[TEST 3]${NC} Verificando dependencias..."
if grep -q "fastapi" backend/requirements.txt; then
    echo -e "${GREEN}✓${NC} requirements.txt contiene dependencias"
    ((PASS_COUNT++))
else
    echo -e "${RED}✗${NC} requirements.txt inválido"
    ((FAIL_COUNT++))
fi

# Test 4: Estructura de directorios
echo ""
echo -e "${YELLOW}[TEST 4]${NC} Verificando estructura..."
DIRS=("backend" "web" "frontend" "backend/app" "backend/app/api" "web/js" "web/css")
for dir in "${DIRS[@]}"; do
    if [ -d "$dir" ]; then
        echo -e "${GREEN}✓${NC} $dir"
        ((PASS_COUNT++))
    else
        echo -e "${RED}✗${NC} $dir no existe"
        ((FAIL_COUNT++))
    fi
done

# Test 5: Archivos clave
echo ""
echo -e "${YELLOW}[TEST 5]${NC} Verificando archivos clave..."
FILES=("backend/main.py" "backend/app/models.py" "web/index.html" "docker-compose.yml")
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} $file"
        ((PASS_COUNT++))
    else
        echo -e "${RED}✗${NC} $file no existe"
        ((FAIL_COUNT++))
    fi
done

# Test 6: Docker
echo ""
echo -e "${YELLOW}[TEST 6]${NC} Verificando Docker..."
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version)
    echo -e "${GREEN}✓${NC} $DOCKER_VERSION"
    ((PASS_COUNT++))
else
    echo -e "${YELLOW}⚠${NC} Docker no instalado (opcional)"
fi

# Test 7: MariaDB
echo ""
echo -e "${YELLOW}[TEST 7]${NC} Verificando conectividad MariaDB..."
if command -v mysql &> /dev/null; then
    if mysql -h 127.0.0.1 -u root -proot -e "SELECT 1" &>/dev/null; then
        echo -e "${GREEN}✓${NC} MariaDB accesible"
        ((PASS_COUNT++))
    else
        echo -e "${YELLOW}⚠${NC} MariaDB no responde (puede estar apagado)"
    fi
else
    echo -e "${YELLOW}⚠${NC} mysql-client no instalado"
fi

# Test 8: Puertos disponibles
echo ""
echo -e "${YELLOW}[TEST 8]${NC} Verificando puertos..."
PORTS=(8000 3306 3000 80 443)
for port in "${PORTS[@]}"; do
    if ! lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        echo -e "${GREEN}✓${NC} Puerto $port disponible"
        ((PASS_COUNT++))
    else
        echo -e "${YELLOW}⚠${NC} Puerto $port en uso"
    fi
done

# Resumen
echo ""
echo "=========================================="
echo -e "RESULTADO: ${GREEN}$PASS_COUNT PASADOS${NC}, ${RED}$FAIL_COUNT FALLIDOS${NC}"
echo "=========================================="
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo -e "${GREEN}✓ Sistema listo para inicial${NC}"
    echo ""
    echo "Próximos pasos:"
    echo "  1. cd backend"
    echo "  2. source venv/bin/activate  # o venv\\Scripts\\activate en Windows"
    echo "  3. pip install -r requirements.txt"
    echo "  4. uvicorn main:app --reload"
    echo ""
    echo "Panel web: http://localhost:8000"
    exit 0
else
    echo -e "${RED}✗ Faltan configuraciones${NC}"
    echo "Revisa los errores arriba y ejecuta los comandos sugeridos"
    exit 1
fi
