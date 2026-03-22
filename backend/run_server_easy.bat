@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHONPATH=%CD%"
set "API_DEBUG=False"

echo Iniciando servidor Database Manager...
if exist ".\venv\Scripts\python.exe" (
    .\venv\Scripts\python.exe main.py
) else (
    python main.py
)
exit /b %errorlevel%
