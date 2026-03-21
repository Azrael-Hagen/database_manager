@echo off
REM Quick Start Script para Database Manager en Windows CMD
REM Más simple que PowerShell, compatibilidad garantizada

setlocal enabledelayedexpansion

color 0A
echo.
echo ========================================
echo Database Manager - Quick Start
echo Windows Command Prompt
echo ========================================
echo.

CD /D "%~dp0"

REM Verificar Python
echo [1/5] Verificando Python...
python --version >nul 2>&1
if errorlevel 1 (
    color 0C
    echo [ERROR] Python no encontrado
    echo Descargalo desde: https://www.python.org
    pause
    exit /b 1
)
echo [OK] Python instalado

REM Crear venv
echo [2/5] Configurando entorno virtual...
if not exist "backend\venv" (
    python -m venv backend\venv
    echo [OK] venv creado
) else (
    echo [OK] venv ya existe
)

REM Activar venv
echo [3/5] Activando entorno virtual...
call backend\venv\Scripts\activate.bat

REM Instalar dependencias
echo [4/5] Instalando dependencias...
python -m pip install -q --upgrade pip
pip install -q -r backend\requirements.txt
if errorlevel 1 (
    color 0C
    echo [ERROR] No se pudieron instalar dependencias
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas

REM Iniciar servidor
echo [5/5] Iniciando FastAPI...
echo.
echo ========================================
echo Servidor FastAPI iniciando...
echo Web:     http://localhost:8000
echo Docs:    http://localhost:8000/docs
echo ReDoc:   http://localhost:8000/redoc
echo ========================================
echo.

cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

pause
