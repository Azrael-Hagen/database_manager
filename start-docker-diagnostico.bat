@echo off
REM Script ROBUSTO para iniciar Database Manager con Docker
REM Incluye captura de logs para debugging

setlocal enabledelayedexpansion
color 0A

REM Variables globales
set "PROJECT_DIR=%~dp0"
set "LOG_FILE=%PROJECT_DIR%diagnostico.log"
set "DOCKER_LOG=%PROJECT_DIR%docker_build.log"
set "MAX_RETRIES=3"
set "WAIT_TIME=5"

goto main

:main
cls
echo.
echo ========================================
echo Database Manager - Docker Auto Start
echo Windows Command Prompt
echo ========================================
echo.
echo [INFO] Logs se guardarán en: %LOG_FILE%
echo.

REM Inicializar log
(
    echo ========================================
    echo Database Manager - Diagnostico
    echo Fecha: %date% %time%
    echo ========================================
    echo.
) > "%LOG_FILE%"

REM Verificar Docker
echo [PASO 1/5] Verificando Docker...
call :check_docker
if errorlevel 1 goto handle_docker_error

REM Verificar docker-compose
echo [PASO 2/5] Verificando docker-compose...
call :check_compose
if errorlevel 1 goto handle_compose_error

REM Diagnostico previo
echo [PASO 3/5] Recogiendo información de diagnóstico...
call :gather_diagnostics

REM Limpiar intentos previos
echo [PASO 4/5] Preparando ambiente...
call :cleanup_old_instances

REM Matar procesos Docker atascados específicamente
echo [PASO 4.5/5] Forzando reinicio de Docker...
call :force_docker_restart

REM Construir e iniciar
echo [PASO 5/6] Iniciando servicios (puede tardar 2-3 minutos)...
call :start_services
if errorlevel 1 goto handle_start_error

REM Éxito
call :success
exit /b 0

REM ===== FUNCIONES =====

:check_docker
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker no encontrado o no ejecutándose
    exit /b 1
)
echo [OK] Docker instalado y disponible
exit /b 0

:check_compose
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] docker-compose no encontrado
    exit /b 1
)
echo [OK] docker-compose disponible
exit /b 0

:gather_diagnostics
echo [Recopilando información de diagnóstico...]
(
    echo.
    echo ========== INFORMACION DEL SISTEMA ==========
    echo Directorio: %cd%
    echo.
    echo ===== Docker Version =====
)  >> "%LOG_FILE%"

docker --version >> "%LOG_FILE%" 2>&1
echo. >> "%LOG_FILE%"

(
    echo ===== Docker Compose Version =====
) >> "%LOG_FILE%"

docker-compose --version >> "%LOG_FILE%" 2>&1
echo. >> "%LOG_FILE%"

(
    echo ===== Docker Info =====
) >> "%LOG_FILE%"

docker info >> "%LOG_FILE%" 2>&1
echo. >> "%LOG_FILE%"

(
    echo ===== Docker Containers =====
) >> "%LOG_FILE%"

docker ps -a >> "%LOG_FILE%" 2>&1
echo. >> "%LOG_FILE%"

(
    echo ===== Docker Images =====
) >> "%LOG_FILE%"

docker images >> "%LOG_FILE%" 2>&1
echo. >> "%LOG_FILE%"

(
    echo ===== Docker Volumes =====
) >> "%LOG_FILE%"

docker volume ls >> "%LOG_FILE%" 2>&1
echo. >> "%LOG_FILE%"

(
    echo ===== Docker Networks =====
) >> "%LOG_FILE%"

docker network ls >> "%LOG_FILE%" 2>&1
echo. >> "%LOG_FILE%"

(
    echo ===== docker-compose.yml =====
) >> "%LOG_FILE%"

type "%PROJECT_DIR%docker-compose.yml" >> "%LOG_FILE%" 2>&1
echo. >> "%LOG_FILE%"

(
    echo ===== .env =====
) >> "%LOG_FILE%"

type "%PROJECT_DIR%.env" >> "%LOG_FILE%" 2>&1
echo. >> "%LOG_FILE%"

echo [OK] Información recopilada
exit /b 0

:cleanup_old_instances
REM Detener instancias previas y matar procesos Docker atascados
echo [Deteniendo servicios previos...]
docker-compose down >nul 2>&1

REM Matar procesos Docker atascados
echo [Matando procesos Docker atascados...]
powershell -Command "Get-Process | Where-Object { $_.Name -like '*docker*' -or $_.ProcessName -like '*com.docker*' } | Stop-Process -Force -ErrorAction SilentlyContinue" 2>nul

REM Limpiar redes colgadas
docker network prune -f >nul 2>&1

REM Limpiar archivos temporales del proyecto
echo [Limpiando archivos temporales...]
powershell -Command "Get-ChildItem -Path '.' -Recurse -Include '*.log', '*.pyc', '__pycache__', '*.tmp', '*.temp' -ErrorAction SilentlyContinue | Where-Object { $_.FullName -notlike '*node_modules*' } | Remove-Item -Force -Recurse -ErrorAction SilentlyContinue" 2>nul

echo [OK] Ambiente preparado
exit /b 0

:force_docker_restart
REM Intentar iniciar Docker Desktop si no está corriendo
echo [Verificando Docker Desktop...]
powershell -Command "Start-Process 'C:\Program Files\Docker\Docker\Docker Desktop.exe' -WindowStyle Hidden" 2>nul

REM Esperar un poco para que inicie
echo [Esperando que Docker Desktop inicie...]
timeout /t 10 /nobreak

REM Verificar si ahora funciona
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ADVERTENCIA] Docker aún no responde, pero continuamos...
) else (
    echo [OK] Docker Desktop iniciado correctamente
)
exit /b 0

:start_services
cd /d "%PROJECT_DIR%"
setlocal enabledelayedexpansion

set "retry=0"
:retry_start
if !retry! geq %MAX_RETRIES% (
    (
        echo.
        echo ========== INTENTO FINAL FALLÓ ==========
        echo Fecha: %date% %time%
        echo Comando: docker-compose up -d --build
        echo.
    ) >> "%LOG_FILE%"
    type "%DOCKER_LOG%" >> "%LOG_FILE%" 2>&1
    echo [ERROR] No se pudieron iniciar servicios después de %MAX_RETRIES% intentos
    exit /b 1
)

set /a retry=!retry!+1
echo [REINTENTO !retry!/%MAX_RETRIES%] Iniciando docker-compose up...

(
    echo.
    echo ========== INTENTO !retry! ==========
    echo Fecha: %date% %time%
    echo.
) >> "%LOG_FILE%"

docker-compose up -d --build > "%DOCKER_LOG%" 2>&1
if errorlevel 1 (
    echo [ADVERTENCIA] docker-compose falló, analizando error...
    
    REM Guardar error en log
    (
        echo Salida de docker-compose:
        echo ----
    ) >> "%LOG_FILE%"
    type "%DOCKER_LOG%" >> "%LOG_FILE%" 2>&1
    (
        echo ----
        echo.
    ) >> "%LOG_FILE%"
    
    REM Intentar soluciones automáticas
    if !retry! equ 1 (
        echo [ACCIÓN] Limpiando volúmenes huérfanos...
        docker volume prune -f >nul 2>&1
        goto retry_start
    )
    
    if !retry! equ 2 (
        echo [ACCIÓN] Eliminando contenedores antiguos...
        docker-compose down -v >nul 2>&1
        timeout /t %WAIT_TIME% /nobreak
        goto retry_start
    )
    
    echo [ERROR] No se pueden iniciar servicios
    exit /b 1
)

echo [OK] Servicios iniciados
(
    echo Servicios iniciados exitosamente en intento !retry!
    echo.
) >> "%LOG_FILE%"
del "%DOCKER_LOG%" >nul 2>&1
exit /b 0

:success
cls
echo.
echo ========================================
echo   [EXITO] Database Manager Running!
echo ========================================
echo.
echo WEB:
echo   URL:                http://localhost:8000
echo   Swagger Docs:       http://localhost:8000/docs
echo   ReDoc:              http://localhost:8000/redoc
echo.
echo CREDENCIALES:
echo   Usuario:            admin
echo   Contraseña:         SecurePassword123!
echo.
echo BASE DE DATOS:
echo   Host:               localhost:3306
echo   Usuario:            manager
echo   Contraseña:         manager123
echo   BD:                 database_manager
echo.
echo COMANDOS UTILES:
echo   Ver logs:           docker-compose logs -f
echo   Ver estado:         docker-compose ps
echo   Detener:            docker-compose down
echo   Limpiar todo:       docker-compose down -v
echo.
echo Abre http://localhost:8000 en tu navegador
echo.
pause
exit /b 0

:handle_docker_error
color 0C
echo.
echo ========================================
echo [ERROR CRITICO] Docker no encontrado
echo ========================================
echo.
echo Soluciones:
echo 1. Descarga Docker Desktop:
echo    https://www.docker.com/products/docker-desktop
echo.
echo 2. Abre Docker Desktop y espera a que esté listo
echo    (verás icono en la bandeja del sistema)
echo.
echo 3. Luego vuelve a ejecutar este script
echo.
pause
exit /b 1

:handle_compose_error
color 0C
echo.
echo ========================================
echo [ERROR] docker-compose no encontrado
echo ========================================
echo.
echo Soluciones:
echo 1. Reinstala Docker Desktop (incluye docker-compose)
echo 2. O instala docker-compose manualmente:
echo    https://docs.docker.com/compose/install/
echo.
pause
exit /b 1

:handle_start_error
color 0C
echo.
echo ========================================
echo [ERROR] No se pudieron iniciar servicios
echo ========================================
echo.
echo DIAGNOSTICO COMPLETO GUARDADO:
echo   Archivo: %LOG_FILE%
echo.
echo PASOS SIGUIENTES:
echo.
echo 1. Abre el archivo con el Bloc de notas:
echo    %LOG_FILE%
echo    (O simplemente busca "diagnostico.log" en tu explorador)
echo.
echo 2. Copia TODA la información del archivo
echo.
echo 3. Pégame el contenido COMPLETO en el chat junto con:
echo    - Esta ventana de error que ves ahora
echo    - Qué pasos ya has intentado
echo.
echo MIENTRAS TANTO, INTENTA ESTO MANUALMENTE:
echo.
echo   docker system prune -a -f
echo   docker-compose down -v
echo   docker-compose logs
echo.
echo El archivo diagnostico.log contiene:
echo   - Versiones de Docker y docker-compose
echo   - Estado actual de contenedores
echo   - Imágenes disponibles
echo   - Volúmenes y redes
echo   - Contenido de docker-compose.yml
echo   - Contenido de .env
echo   - Errores de cada intento
echo.
pause
exit /b 1
