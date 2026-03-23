param(
    [ValidateSet("deploy", "status", "switch")]
    [string]$Action = "deploy",
    [ValidateSet("blue", "green")]
    [string]$Color,
    [string]$ComposeFile = "docker-compose.bluegreen.yml",
    [string]$ActiveFile = "deploy/active-upstream.conf",
    [int]$MaxAttempts = 40,
    [int]$WaitSeconds = 2,
    [switch]$SkipBuild,
    [switch]$NoRollback
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot
$LogsDir = Join-Path $ProjectRoot "logs"
if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir | Out-Null
}
$LogFile = Join-Path $LogsDir ("deploy-bluegreen-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".log")

function Write-Info([string]$Message) {
    $line = "[INFO] $Message"
    Write-Host $line -ForegroundColor Cyan
    Add-Content -Path $LogFile -Value $line
}

function Write-Ok([string]$Message) {
    $line = "[OK] $Message"
    Write-Host $line -ForegroundColor Green
    Add-Content -Path $LogFile -Value $line
}

function Write-Warn([string]$Message) {
    $line = "[WARN] $Message"
    Write-Host $line -ForegroundColor Yellow
    Add-Content -Path $LogFile -Value $line
}

function Write-Err([string]$Message) {
    $line = "[ERROR] $Message"
    Write-Host $line -ForegroundColor Red
    Add-Content -Path $LogFile -Value $line
}

function Test-DockerDaemon {
    $oldPref = $PSNativeCommandUseErrorActionPreference
    try {
        $PSNativeCommandUseErrorActionPreference = $false
        docker info *> $null
        return ($LASTEXITCODE -eq 0)
    } finally {
        $PSNativeCommandUseErrorActionPreference = $oldPref
    }
}

function Assert-Prerequisites {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker no está instalado o no está en PATH."
    }
    if (-not (Test-Path $ComposeFile)) {
        throw "No se encontró el archivo de compose: $ComposeFile"
    }
    if (-not (Test-DockerDaemon)) {
        throw "Docker daemon no disponible. Inicia Docker Desktop (o servicio docker) e intenta de nuevo."
    }
    $activeDir = Split-Path -Parent $ActiveFile
    if ($activeDir -and -not (Test-Path $activeDir)) {
        New-Item -ItemType Directory -Path $activeDir | Out-Null
    }
    if (-not (Test-Path $ActiveFile)) {
        Set-Content -Path $ActiveFile -Value "proxy_pass http://backend_blue:8000;`n" -Encoding UTF8
        Write-Info "No existía $ActiveFile; se creó con backend_blue por defecto."
    }
}

function Get-ActiveColor {
    if (-not (Test-Path $ActiveFile)) {
        return "blue"
    }
    $content = Get-Content $ActiveFile -Raw
    if ($content -match "backend_green") {
        return "green"
    }
    return "blue"
}

function Set-ActiveColor([string]$TargetColor) {
    if ($TargetColor -eq "blue") {
        Set-Content -Path $ActiveFile -Value "proxy_pass http://backend_blue:8000;`n" -Encoding UTF8
    } else {
        Set-Content -Path $ActiveFile -Value "proxy_pass http://backend_green:8000;`n" -Encoding UTF8
    }
    docker compose -f $ComposeFile up -d gateway | Out-Null
    docker compose -f $ComposeFile exec gateway nginx -s reload | Out-Null
}

function Wait-Healthy([string]$TargetColor, [int]$Attempts, [int]$DelaySeconds) {
    $port = if ($TargetColor -eq "blue") { 18000 } else { 18001 }
    for ($i = 1; $i -le $Attempts; $i++) {
        try {
            $res = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:$port/api/health" -TimeoutSec 3
            if ($res.status -eq "ok") {
                return $true
            }
        } catch {
            Start-Sleep -Seconds $DelaySeconds
        }
    }
    return $false
}

function Get-DeployStatus {
    Assert-Prerequisites
    $active = Get-ActiveColor
    Write-Info "Active color: $active"
    docker compose -f $ComposeFile ps
    Write-Info "Log: $LogFile"
}

switch ($Action) {
    "status" {
        Get-DeployStatus
        exit 0
    }

    "switch" {
        Assert-Prerequisites
        if (-not $Color) {
            throw "Para switch debes indicar -Color blue|green"
        }
        Write-Info "Cambiando tráfico a $Color"
        Set-ActiveColor -TargetColor $Color
        Write-Ok "Switch completado a $Color"
        Get-DeployStatus
        exit 0
    }

    "deploy" {
        Assert-Prerequisites
        $active = Get-ActiveColor
        $target = if ($active -eq "blue") { "green" } else { "blue" }
        $oldService = if ($target -eq "blue") { "backend_green" } else { "backend_blue" }
        $targetService = "backend_" + $target

        Write-Info "Color activo actual: $active"
        Write-Info "Color objetivo: $target"
        Write-Info "Levantando dependencias base (mariadb + gateway)"
        docker compose -f $ComposeFile up -d mariadb gateway | Out-Null

        if ($SkipBuild) {
            Write-Info "Levantando $targetService sin build"
            docker compose -f $ComposeFile up -d $targetService | Out-Null
        } else {
            Write-Info "Levantando $targetService con build"
            docker compose -f $ComposeFile up -d --build $targetService | Out-Null
        }

        Write-Info "Esperando healthcheck de $targetService"
        if (-not (Wait-Healthy -TargetColor $target -Attempts $MaxAttempts -DelaySeconds $WaitSeconds)) {
            $message = "El backend $target no pasó healthcheck en tiempo esperado."
            Write-Err $message
            throw $message
        }

        try {
            Set-ActiveColor -TargetColor $target
            Write-Ok "Switch de tráfico aplicado a $target"
        } catch {
            Write-Err "Falló el switch de tráfico hacia ${target}: $($_.Exception.Message)"
            if (-not $NoRollback) {
                Write-Warn "Intentando rollback hacia $active"
                Set-ActiveColor -TargetColor $active
                Write-Ok "Rollback aplicado a $active"
            }
            throw
        }

        if (-not $NoRollback) {
            Write-Info "Deteniendo servicio anterior: $oldService"
            docker compose -f $ComposeFile stop $oldService | Out-Null
        }

        Write-Ok "Deploy sin downtime completado. Activo: $target"
        Get-DeployStatus
        exit 0
    }
}
