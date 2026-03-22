@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul

REM Inicio simple para usuarios no tecnicos
set "ROOT=%~dp0"
set "PORT=8000"
set "URL=http://localhost:%PORT%"

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
    echo [OK] El servidor ya estaba activo en %URL%
    start "" "%URL%"
    exit /b 0
)

echo [1/3] Iniciando servidor en una nueva ventana...
if not exist "%ROOT%backend\run_server_easy.bat" (
    echo [ERROR] No se encontró backend\run_server_easy.bat
    pause
    exit /b 1
)
start "Database Manager Server" "%ROOT%backend\run_server_easy.bat"

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

:open_ui
echo [3/3] Abriendo interfaz: %URL%
start "" "%URL%"
echo.
echo [OK] Inicio completado.
echo Para detener el servidor usa: stop.bat
exit /b 0
