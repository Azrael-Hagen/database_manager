@echo off
REM Database Manager - Script de Inicio Único
REM Windows - Python + MariaDB

setlocal enabledelayedexpansion
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
title Database Manager - Consola UTF-8
mode con cols=130 lines=38
color 0A

echo.
echo ========================================
echo Database Manager - Inicio Rapido
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
    echo Descargalo desde https://www.python.org
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
        echo SOLUCION:
        echo Lee INSTALAR-MARIADB.md para instalar MariaDB
        echo.
        pause
        exit /b 1
    )
    echo [OK] MariaDB disponible
)

echo.
choice /C SN /N /M "Configurar acceso http://phantom.database.local sin puerto? [S/N]: "
if errorlevel 2 goto skip_host_setup
if errorlevel 1 (
    echo [INFO] Ejecutando configuracion de host local; puede pedir permisos de administrador...
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup-phantom-host.ps1"
    if errorlevel 1 (
        echo [AVISO] No se completo la configuracion de host. Se continuara con el arranque normal.
    )
)

:skip_host_setup

REM Preguntar sobre HTTPS
if exist "%~dp0ssl\cert.pem" (
    echo [OK] Certificados TLS detectados. HTTPS estara activo en el puerto 8443.
    echo      Accede via: https://phantom.database.local
    goto skip_https_setup
)
echo.
choice /C SN /N /M "Configurar HTTPS con certificado TLS (para camara en red)? [S/N]: "
if errorlevel 2 goto skip_https_setup
if errorlevel 1 (
    echo [INFO] Configurando HTTPS; requiere permisos de administrador...
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup-https.ps1"
    if errorlevel 1 (
        echo [AVISO] No se pudo configurar HTTPS. Continuando solo con HTTP.
    )
)

:skip_https_setup

REM Iniciar aplicación
echo [PASO 3/3] Iniciando Database Manager...
echo.
echo ========================================
echo   APLICACION INICIANDO...
echo ========================================
echo.
echo URL:              http://localhost:8000
echo Documentacion:    http://localhost:8000/docs
echo Stop rapido:      .\stop.bat
echo Frontend activo:  carpeta web\ (no frontend\)
echo Usuario:          admin
echo Contrasena:       Admin123!
echo.
echo Presiona Ctrl+C para detener
echo.

REM Verificar si ya existe un proceso escuchando en el puerto configurado
set "PIDS="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":8000 .*LISTENING"') do (
    if not defined PIDS (
        set "PIDS=%%P"
    ) else (
        echo !PIDS! | findstr /R /C:"\<%%P\>" >nul || set "PIDS=!PIDS! %%P"
    )
)

if defined PIDS (
    echo [AVISO] Ya hay procesos escuchando en el puerto 8000.
    echo PIDs: !PIDS!
    echo.
    powershell -NoProfile -Command "$ids='!PIDS!'.Split(' ',[System.StringSplitOptions]::RemoveEmptyEntries) ^| ForEach-Object { [int]$_ }; Get-CimInstance Win32_Process ^| Where-Object { $ids -contains $_.ProcessId } ^| Select-Object ProcessId, CommandLine ^| Format-Table -AutoSize"
    echo.
    echo Opciones:
    echo   1. Reutilizar la sesion actual
    echo   2. Reiniciar y crear una sesion nueva
    echo   3. Detener sesiones y salir
    echo   4. Cancelar
    choice /C 1234 /N /M "Elige una opcion [1/2/3/4]: "

    if errorlevel 4 exit /b 0
    if errorlevel 3 goto stop_existing_and_exit
    if errorlevel 2 goto kill_existing_session
    if errorlevel 1 (
        echo [OK] Reutilizando la sesion activa en http://localhost:8000
        exit /b 0
    )
)

goto run_server

:kill_existing_session
echo.
echo Cerrando sesiones activas...
for %%P in (!PIDS!) do (
    taskkill /PID %%P /T /F >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] No se pudo cerrar el proceso %%P
        exit /b 1
    )
    echo [OK] Proceso %%P cerrado
)
timeout /t 2 /nobreak >nul

set "REMAINING="
for /f "tokens=5" %%R in ('netstat -ano ^| findstr /R /C:":8000 .*LISTENING"') do set "REMAINING=1"
if defined REMAINING (
    echo [ERROR] El puerto 8000 sigue ocupado.
    exit /b 1
)
echo [OK] Puerto 8000 liberado

goto run_server

:stop_existing_and_exit
echo.
echo Deteniendo sesiones activas...
for %%P in (!PIDS!) do (
    taskkill /PID %%P /T /F >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] No se pudo cerrar el proceso %%P
        exit /b 1
    )
    echo [OK] Proceso %%P cerrado
)
echo [OK] Sesiones detenidas.
exit /b 0

:run_server

REM Ejecutar aplicacion por main.py para respetar Ctrl+C
cd backend
set "PYTHONPATH=%CD%"
set "API_DEBUG=False"
python main.py
exit /b %errorlevel%
