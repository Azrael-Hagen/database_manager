@echo off
REM Script ROBUSTO para iniciar Database Manager con Docker
REM Incluye detección de errores y soluciones automáticas

setlocal enabledelayedexpansion
color 0A

REM Variables globales
set "PROJECT_DIR=%~dp0"
set "MAX_RETRIES=3"
set "WAIT_TIME=5"
set "SUCCESS=0"

REM Colores
set "RED=[91m"
set "GREEN=[92m"
set "YELLOW=[93m"

goto main

:main
cls
echo.
echo ========================================
echo Database Manager - Docker Auto Start
echo Windows Command Prompt
echo ========================================
echo.

REM Verificar Docker
echo [PASO 1/5] Verificando Docker...
call :check_docker
if errorlevel 1 goto handle_docker_error

REM Verificar docker-compose
echo [PASO 2/5] Verificando docker-compose...
call :check_compose
if errorlevel 1 goto handle_compose_error

REM Limpiar intentos previos (opcional)
echo [PASO 3/5] Preparando ambiente...
call :cleanup_old_instances

REM Construir e iniciar
echo [PASO 4/5] Iniciando servicios (puede tardar 2-3 minutos)...
call :start_services
if errorlevel 1 goto handle_start_error

REM Verificar que servicios están arriba
echo [PASO 5/5] Verificando servicios...
call :verify_services
if errorlevel 1 goto handle_verify_error

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

:cleanup_old_instances
REM Detener instancias previas si existen
docker-compose down >nul 2>&1
REM Limpiar redes colgadas
docker network prune -f >nul 2>&1
echo [OK] Ambiente preparado
exit /b 0

:start_services
cd /d "%PROJECT_DIR%"
setlocal enabledelayedexpansion

set "retry=0"
:retry_start
if !retry! geq %MAX_RETRIES% (
    echo [ERROR] No se pudieron iniciar servicios después de %MAX_RETRIES% intentos
    exit /b 1
)

set /a retry=!retry!+1
echo [REINTENTO %retry%/%MAX_RETRIES%] Iniciando docker-compose up...

docker-compose up -d --build >temp_docker_build.log 2>&1
if errorlevel 1 (
    echo [ADVERTENCIA] docker-compose falló, analizando error...
    
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
    type temp_docker_build.log
    del temp_docker_build.log
    exit /b 1
)

echo [OK] Servicios iniciados
del temp_docker_build.log >nul 2>&1
exit /b 0

:verify_services
setlocal enabledelayedexpansion
set "max_wait=60"
set "waited=0"

:wait_loop
cls
echo.
echo ========================================
echo Database Manager - Esperando servicios
echo Tiempo de espera: !waited!/%max_wait% segundos
echo ========================================
echo.

docker-compose ps

REM Verificar que ambos servicios estén arriba
docker-compose ps | findstr "database_manager_db" >nul 2>&1 && (
    docker-compose ps | findstr "database_manager_api" >nul 2>&1 && (
        goto verify_health
    )
)

REM Si no están arriba, esperar más
if !waited! geq %max_wait% (
    echo [ERROR] Servicios no iniciaron en tiempo
    exit /b 1
)

set /a waited=!waited!+1
timeout /t 1 /nobreak
goto wait_loop

:verify_health
REM Verificar healthcheck de MariaDB
echo.
echo [Verificando MariaDB...]
docker-compose exec -T mariadb mariadb-admin ping -h localhost >nul 2>&1
if errorlevel 1 (
    if !waited! geq %max_wait% (
        echo [ERROR] MariaDB no responde al ping
        exit /b 1
    )
    set /a waited=!waited!+1
    timeout /t 2 /nobreak
    goto verify_health
)

echo [OK] MariaDB está listo
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
echo Soluciones automáticas intentadas:
echo 1. Se limpió volúmenes huérfanos
echo 2. Se eliminaron contenedores antiguos
echo.
echo Pruebas manuales adicionales:
echo 1. Verifica que puertos 8000 y 3306 no estén en uso:
echo    netstat -ano ^| findstr :8000
echo    netstat -ano ^| findstr :3306
echo.
echo 2. Reinicia Docker Desktop completamente
echo.
echo 3. Reset completo:
echo    docker-compose down -v
echo    docker system prune -a -f
echo.
pause
exit /b 1

:handle_verify_error
color 0C
echo.
echo ========================================
echo [ERROR] Servicios no iniciaron correctamente
echo ========================================
echo.
echo Mira los logs:
echo   docker-compose logs
echo.
echo Prueba:
echo   docker-compose ps
echo.
pause
exit /b 1

