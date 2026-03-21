#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Script de despliegue automático para Database Manager en Windows
.DESCRIPTION
    Configura completamente el proyecto incluyendo venv, dependencias e inicialización de BD
#>

# Configuración
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $ProjectRoot "backend"
$VenvDir = Join-Path $BackendDir "venv"
$RequirementsFile = Join-Path $BackendDir "requirements.txt"
$PythonExe = Join-Path $VenvDir "Scripts" "python.exe"
$UvicornCmd = Join-Path $VenvDir "Scripts" "uvicorn.exe"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Database Manager - Deployment Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Función para verificar comandos
function Test-Command {
    param($Command)
    try {
        if (Get-Command $Command -ErrorAction Stop) {
            return $true
        }
    }
    catch {
        return $false
    }
}

# Verificar Python
Write-Host "[1] Verificando requisitos..." -ForegroundColor Yellow

if (-not (Test-Command python)) {
    Write-Host "❌ Python no está instalado o no está en PATH" -ForegroundColor Red
    Write-Host "Descarga desde: https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}

$pythonVersion = python --version 2>&1
Write-Host "✓ $pythonVersion" -ForegroundColor Green

# Crear .env si no existe
Write-Host ""
Write-Host "[2] Configurar variables de entorno..." -ForegroundColor Yellow

if (-not (Test-Path ".env")) {
    Write-Host "Creando .env..." -ForegroundColor Green
    Copy-Item ".env.example" ".env"
    Write-Host "⚠️ IMPORTANTE: Edita .env con tus configuraciones" -ForegroundColor Yellow
    Start-Process notepad ".env"
    Read-Host "Presiona Enter cuando hayas guardado .env"
}
else {
    Write-Host "✓ .env ya existe" -ForegroundColor Green
}

# Entorno virtual
Write-Host ""
Write-Host "[3] Preparar entorno Python..." -ForegroundColor Yellow

if (-not (Test-Path "backend\venv")) {
    Write-Host "Creando venv..." -ForegroundColor Green
    cd backend
    python -m venv venv
    cd ..
}

# Activar venv
& "backend\venv\Scripts\Activate.ps1"

# Instalar dependencias
Write-Host "Instalando dependencias..." -ForegroundColor Green
pip install -r backend\requirements.txt -q

# Inicializar BD
Write-Host ""
Write-Host "[4] Inicializar base de datos..." -ForegroundColor Yellow
cd backend
python init_db.py
cd ..

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "✅ DEPLOYMENT COMPLETADO" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "📊 Para iniciar el servidor:" -ForegroundColor Cyan
Write-Host "   cd backend" -ForegroundColor White
Write-Host "   python main.py" -ForegroundColor White
Write-Host ""
Write-Host "📖 Documentación disponible en:" -ForegroundColor Cyan
Write-Host "   • API: http://localhost:8000/docs" -ForegroundColor White
Write-Host "   • Panel: http://localhost:8000" -ForegroundColor White
Write-Host ""
