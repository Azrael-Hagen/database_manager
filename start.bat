@echo off
REM Database Manager - Script de Inicio Único
REM Windows - Python + MariaDB

setlocal enabledelayedexpansion
color 0A

echo.
echo ========================================
echo Database Manager - Inicio Rápido
echo Python 3.14.3 + MariaDB 12.2.2
echo ========================================
echo.

CD /D "%~dp0"

REM Verificar Python
echo [PASO 1/3] Verificando Python...
python --version >nul 2>&1
if errorlevel 1 (
    color 0C
    echo [ERROR] Python no encontrado
    echo Descargalo desde: https://www.python.org
    pause
    exit /b 1
)
echo [OK] Python disponible

REM Verificar MariaDB
echo [PASO 2/3] Verificando MariaDB...
if exist "C:\Program Files\MariaDB 12.2\bin\mysql.exe" (
    "C:\Program Files\MariaDB 12.2\bin\mysql.exe" --version >nul 2>&1
    if errorlevel 1 (
        color 0C
        echo [ERROR] MariaDB instalado pero no funciona
        echo Verifica la instalación
        pause
        exit /b 1
    )
    echo [OK] MariaDB disponible
) else (
    mysql --version >nul 2>&1
    if errorlevel 1 (
        color 0C
        echo [ERROR] MariaDB no encontrado
        echo.
        echo SOLUCIÓN:
        echo Lee INSTALAR-MARIADB.md para instalar MariaDB
        echo.
        pause
        exit /b 1
    )
    echo [OK] MariaDB disponible
)

REM Iniciar aplicación
echo [PASO 3/3] Iniciando Database Manager...
echo.
echo ========================================
echo   APLICACIÓN INICIANDO...
echo ========================================
echo.
echo URL:              http://localhost:8000
echo Documentación:    http://localhost:8000/docs
echo Usuario:          admin
echo Contraseña:       Admin123!
echo.
echo Presiona Ctrl+C para detener
echo.

REM Ejecutar aplicación
"C:/Users/Azrael/AppData/Local/Python/pythoncore-3.14-64/python.exe" "backend/main.py"

pause
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
