@echo off
REM Quick Start Script para Database Manager en Windows CMD
REM Usa venv para aislamiento de dependencias

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
set "VENV_DIR=%~dp0backend\venv"
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [ERROR] No se encontró %VENV_DIR%\Scripts\activate.bat
    pause
    exit /b 1
)
call "%VENV_DIR%\Scripts\activate.bat"

REM Instalar dependencias con venv
echo [4/5] Instalando dependencias...
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
"%VENV_DIR%\Scripts\python.exe" -m pip install numpy --only-binary :all:
"%VENV_DIR%\Scripts\python.exe" -m pip install pandas --only-binary :all:
"%VENV_DIR%\Scripts\python.exe" -m pip install -r "%~dp0backend\requirements.txt"
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
