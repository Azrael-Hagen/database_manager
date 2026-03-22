@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
echo Creando accesos directos en el escritorio...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\create-desktop-shortcuts.ps1"
if errorlevel 1 (
  echo [ERROR] No se pudieron crear los accesos directos.
  pause
  exit /b 1
)
echo [OK] Accesos directos creados correctamente.
pause
exit /b 0
