@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

set "PORT=8000"
set "PIDS="

echo.
echo ========================================
echo Database Manager - Stop
echo ========================================
echo.

for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do (
    if not defined PIDS (
        set "PIDS=%%P"
    ) else (
        echo !PIDS! | findstr /R /C:"\<%%P\>" >nul || set "PIDS=!PIDS! %%P"
    )
)

if not defined PIDS (
    echo [OK] No hay procesos escuchando en el puerto %PORT%.
    exit /b 0
)

echo [INFO] Procesos detectados en puerto %PORT%: !PIDS!
for %%P in (!PIDS!) do (
    taskkill /PID %%P /T /F >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] No se pudo cerrar el proceso %%P
        exit /b 1
    )
    echo [OK] Proceso %%P cerrado
)

timeout /t 1 /nobreak >nul
for /f "tokens=5" %%R in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do (
    echo [ERROR] El puerto %PORT% sigue ocupado.
    exit /b 1
)

echo [OK] Servidor detenido correctamente.
exit /b 0
