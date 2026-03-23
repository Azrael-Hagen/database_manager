@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if "%~1"=="" goto :usage

set "ACTION=%~1"
set "MODE=%~2"
if "%MODE%"=="" set "MODE=logon"

if /I "%ACTION%"=="install" goto :run
if /I "%ACTION%"=="remove" goto :run
if /I "%ACTION%"=="status" goto :run

goto :usage

:run
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup-autostart.ps1" -Action %ACTION% -Mode %MODE%
exit /b %errorlevel%

:usage
echo Uso:
echo   manage_autostart.bat install [logon^|startup]
echo   manage_autostart.bat remove
echo   manage_autostart.bat status
exit /b 1
