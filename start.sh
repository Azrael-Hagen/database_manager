#!/usr/bin/env bash
# Quick Start Script para Database Manager en Linux/Mac
# Usa los mismos pasos que start.bat pero en shell POSIX.

set -euo pipefail
IFS=$'\n\t'

echo "========================================="
echo "Database Manager - Quick Start"
echo "Linux / macOS"
echo "========================================="

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$PROJECT_ROOT"

echo "[1/5] Verificando Python..."
if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  echo "[ERROR] Python no está instalado. Instala python3."
  exit 1
fi

PYTHON_CMD=python3
if ! command -v python3 >/dev/null 2>&1; then
  PYTHON_CMD=python
fi

$PYTHON_CMD --version

echo "[2/5] Configurando entorno virtual..."
if [ ! -d "backend/venv" ]; then
  $PYTHON_CMD -m venv backend/venv
  echo "[OK] venv creado"
else
  echo "[OK] venv ya existe"
fi

echo "[3/5] Activando entorno virtual..."
source backend/venv/bin/activate

echo "[4/5] Instalando dependencias..."
python -m pip install --upgrade pip
pip install -r backend/requirements.txt

echo "[5/5] Iniciando FastAPI..."
echo "========================================="
echo "Servidor FastAPI iniciando..."
echo "Web:     http://localhost:8000"
echo "Docs:    http://localhost:8000/docs"
echo "ReDoc:   http://localhost:8000/redoc"
echo "========================================="

cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
