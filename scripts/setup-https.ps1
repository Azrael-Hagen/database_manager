param(
    [string]$HostName  = "phantom.database.local",
    [int]$HttpsPort    = 8443,
    [switch]$Elevated
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$SslDir      = Join-Path $ProjectRoot "ssl"

function Test-IsAdmin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    return (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole(
        [Security.Principal.WindowsBuiltinRole]::Administrator)
}

# ── Elevación automática ─────────────────────────────────────────────────────
if (-not (Test-IsAdmin)) {
    Write-Host "[INFO] Se necesitan permisos de administrador. Solicitando elevación..." -ForegroundColor Yellow
    $args = @("-ExecutionPolicy","Bypass","-File","`"$PSCommandPath`"",
              "-HostName","`"$HostName`"","-HttpsPort","$HttpsPort","-Elevated")
    try {
        $p = Start-Process powershell.exe -Verb RunAs -ArgumentList $args -PassThru
        $p.WaitForExit()
        exit $p.ExitCode
    } catch {
        Write-Host "[ERROR] No se pudo elevar. Ejecuta PowerShell como administrador." -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "=== Configuración HTTPS para $HostName ===" -ForegroundColor Cyan
Write-Host ""

# ── 1. Verificar / instalar mkcert ──────────────────────────────────────────
Write-Host "[1/5] Verificando mkcert..." -ForegroundColor Cyan
$mkcert = Get-Command mkcert -ErrorAction SilentlyContinue
if (-not $mkcert) {
    Write-Host "      mkcert no encontrado. Intentando instalar con winget..." -ForegroundColor Yellow
    try {
        winget install --id FiloSottile.mkcert --silent --accept-package-agreements --accept-source-agreements
    } catch {
        Write-Host "[ERROR] winget falló. Descarga mkcert manualmente:" -ForegroundColor Red
        Write-Host "        https://github.com/FiloSottile/mkcert/releases/latest" -ForegroundColor Yellow
        Write-Host "        Coloca mkcert.exe en C:\Windows\System32 y vuelve a ejecutar este script." -ForegroundColor Yellow
        exit 1
    }
    # Refrescar PATH
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("PATH","User")
    $mkcert = Get-Command mkcert -ErrorAction SilentlyContinue
    if (-not $mkcert) {
        Write-Host "[ERROR] mkcert instalado pero no encontrado en PATH." -ForegroundColor Red
        Write-Host "        Reinicia la terminal y vuelve a ejecutar: scripts\setup-https.ps1" -ForegroundColor Yellow
        exit 1
    }
}
Write-Host "[OK] mkcert disponible: $($mkcert.Source)" -ForegroundColor Green

# ── 2. Instalar CA raíz local (una sola vez) ─────────────────────────────────
Write-Host "[2/5] Instalando autoridad de certificación local (CA)..." -ForegroundColor Cyan
mkcert -install
Write-Host "[OK] CA local instalada en el almacén de confianza de Windows/Firefox" -ForegroundColor Green

# ── 3. Generar certificado para el hostname ──────────────────────────────────
Write-Host "[3/5] Generando certificado para '$HostName'..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $SslDir | Out-Null
$certFile = Join-Path $SslDir "cert.pem"
$keyFile  = Join-Path $SslDir "key.pem"

Push-Location $SslDir
try {
    mkcert -cert-file cert.pem -key-file key.pem $HostName localhost 127.0.0.1 "::1"
} finally {
    Pop-Location
}

if (-not (Test-Path $certFile) -or -not (Test-Path $keyFile)) {
    Write-Host "[ERROR] No se generaron los archivos de certificado." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Certificado generado en: $SslDir" -ForegroundColor Green

# ── 4. Port-proxy 443 → HttpsPort ───────────────────────────────────────────
Write-Host "[4/5] Configurando portproxy 443 → $HttpsPort..." -ForegroundColor Cyan
Start-Service iphlpsvc -ErrorAction SilentlyContinue | Out-Null
netsh interface portproxy delete v4tov4 listenport=443 listenaddress=0.0.0.0 2>&1 | Out-Null
netsh interface portproxy add    v4tov4 listenport=443 listenaddress=0.0.0.0 connectport=$HttpsPort connectaddress=127.0.0.1 | Out-Null

$ruleName = "DatabaseManager HTTPS 443"
if (-not (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort 443 | Out-Null
}
Write-Host "[OK] Portproxy activo: :443 → 127.0.0.1:$HttpsPort" -ForegroundColor Green

# ── 5. Actualizar SSL_PORT en .env ─────────────────────────────────────────
Write-Host "[5/5] Actualizando .env con SSL_PORT=$HttpsPort..." -ForegroundColor Cyan
$envFile = Join-Path $ProjectRoot ".env"
if (Test-Path $envFile) {
    $envContent = Get-Content $envFile -Raw
    if ($envContent -match "SSL_PORT\s*=") {
        $envContent = $envContent -replace "SSL_PORT\s*=.*", "SSL_PORT=$HttpsPort"
    } else {
        $envContent = $envContent.TrimEnd() + "`nSSL_PORT=$HttpsPort`n"
    }
    # Agregar HTTPS a CORS_ORIGINS si no está ya
    if ($envContent -notmatch "https://$([regex]::Escape($HostName))") {
        $envContent = $envContent -replace `
            '(CORS_ORIGINS\s*=\s*\[")([^"]*")', `
            "`$1`$2, `"https://$HostName`", `"https://localhost:$HttpsPort`""
    }
    Set-Content -Path $envFile -Value $envContent -Encoding UTF8
    Write-Host "[OK] .env actualizado" -ForegroundColor Green
} else {
    Write-Host "[AVISO] No se encontró .env. Agrega manualmente: SSL_PORT=$HttpsPort" -ForegroundColor Yellow
}

# ── Resumen ──────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  HTTPS configurado correctamente" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Certificado : $certFile" -ForegroundColor White
Write-Host "  Clave       : $keyFile" -ForegroundColor White
Write-Host "  Puerto HTTPS: $HttpsPort  (accesible en :443 via portproxy)" -ForegroundColor White
Write-Host ""
Write-Host "  Próximo paso:" -ForegroundColor Cyan
Write-Host "    Reinicia el servidor con start.bat" -ForegroundColor White
Write-Host "    Luego accede a: https://$HostName" -ForegroundColor White
Write-Host ""
Write-Host "  La cámara funcionará desde cualquier dispositivo en la red" -ForegroundColor Green
Write-Host "  que acceda a: https://$HostName" -ForegroundColor Green
Write-Host ""
