@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul

REM Inicio simple para usuarios no tecnicos
set "ROOT=%~dp0"
set "PORT=8000"
set "URL=http://localhost:%PORT%"
set "MODE=%~1"

title Database Manager - Inicio Facil
color 0B

cd /d "%ROOT%"

echo.
echo ========================================
echo Database Manager - Inicio Facil
echo ========================================
echo.

set "IS_RUNNING="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do set "IS_RUNNING=1"

if defined IS_RUNNING (
    if /I "%MODE%"=="--force-restart" goto :restart_running
    if /I "%MODE%"=="--reuse" goto :reuse_running

    echo [INFO] Hay una sesion activa en %URL%
    choice /C SN /N /M "Reiniciar para aplicar actualizaciones? [S/N]: "
    if errorlevel 2 goto :reuse_running
    if errorlevel 1 goto :restart_running
)

echo [1/3] Iniciando servidor oficial en una nueva ventana...
if not exist "%ROOT%start.bat" (
    echo [ERROR] No se encontró start.bat
    pause
    exit /b 1
)
start "Database Manager Server" "%ROOT%start.bat"

echo [2/3] Esperando disponibilidad del servidor...
set "READY="
for /L %%I in (1,1,90) do (
    set "READY="
    for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do set "READY=1"
    if defined READY goto :open_ui
    timeout /t 1 /nobreak >nul
)

echo [AVISO] No se pudo confirmar el puerto en tiempo esperado.
echo Si el servidor sigue iniciando, espera unos segundos y abre: %URL%
start "" "%URL%"
exit /b 0

:reuse_running
echo [OK] Reutilizando sesion activa en %URL%
start "" "%URL%"
exit /b 0

:restart_running
echo [INFO] Reiniciando servidor para aplicar codigo actualizado...
if exist "%ROOT%stop.bat" (
    call "%ROOT%stop.bat"
)
timeout /t 1 /nobreak >nul
start "Database Manager Server" "%ROOT%start.bat"
echo [OK] Nueva sesion iniciada, esperando disponibilidad...
for /L %%I in (1,1,90) do (
    set "READY="
    for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do set "READY=1"
    if defined READY goto :open_ui
    timeout /t 1 /nobreak >nul
)
echo [AVISO] No se pudo confirmar el puerto en tiempo esperado.
start "" "%URL%"
exit /b 0

:open_ui
echo [3/3] Abriendo interfaz: %URL%
start "" "%URL%"
echo.
echo [OK] Inicio completado.
echo Script oficial de arranque del servidor: start.bat
echo Para detener el servidor usa: stop.bat
exit /b 0
