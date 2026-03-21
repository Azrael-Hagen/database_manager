@echo off
REM Database Manager - Script de Inicio Único
REM Windows - Python + MariaDB

setlocal enabledelayedexpansion
chcp 65001 >nul
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

REM Iniciar aplicación
echo [PASO 3/3] Iniciando Database Manager...
echo.
echo ========================================
echo   APLICACION INICIANDO...
echo ========================================
echo.
echo URL:              http://localhost:8000
echo Documentacion:    http://localhost:8000/docs
echo Frontend activo:  carpeta web\ (no frontend\)
echo Usuario:          admin
echo Contrasena:       Admin123!
echo.
echo Presiona Ctrl+C para detener
echo.

REM Verificar si ya existe un proceso escuchando en el puerto configurado
set "PORT_ACTION=0"
powershell -NoProfile -Command "$port = 8000; $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; if (-not $connections) { exit 0 }; Write-Host '[AVISO] Ya hay procesos escuchando en el puerto 8000.'; Write-Host ('PID(s): ' + ($connections -join ' ')); Write-Host ''; Get-CimInstance Win32_Process | Where-Object { $connections -contains $_.ProcessId } | Select-Object ProcessId, CommandLine | Format-Table -AutoSize | Out-Host; Write-Host ''; Write-Host 'Opciones:'; Write-Host '  1. Reutilizar la sesion actual'; Write-Host '  2. Reiniciar y crear una sesion nueva'; Write-Host '  3. Cancelar'; $answer = Read-Host 'Elige una opcion [1/2/3]'; if ($answer -eq '1') { exit 11 }; if ($answer -eq '3') { exit 12 }; if ($answer -ne '2') { exit 12 }; Write-Host ''; Write-Host 'Cerrando sesiones activas...'; foreach ($procId in $connections) { $result = Start-Process -FilePath taskkill.exe -ArgumentList '/PID', $procId, '/T', '/F' -NoNewWindow -Wait -PassThru; if ($result.ExitCode -ne 0) { Write-Host ('[ERROR] No se pudo cerrar el proceso ' + $procId); exit 2 }; Write-Host ('[OK] Proceso ' + $procId + ' cerrado') }; Start-Sleep -Seconds 2; $remaining = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; if ($remaining) { Write-Host ('[ERROR] El puerto 8000 sigue ocupado por: ' + ($remaining -join ' ')); exit 2 }; Write-Host '[OK] Puerto 8000 liberado'; exit 10"
set "PORT_ACTION=%errorlevel%"

if "%PORT_ACTION%"=="2" exit /b 1
if "%PORT_ACTION%"=="11" (
    echo [OK] Reutilizando la sesion activa en http://localhost:8000
    exit /b 0
)
if "%PORT_ACTION%"=="12" exit /b 0

REM Ejecutar aplicación a través de main.py para respetar el manejador de Ctrl+C
cd backend
set "PYTHONPATH=%CD%"
set "API_DEBUG=False"
python main.py
exit /b %errorlevel%
