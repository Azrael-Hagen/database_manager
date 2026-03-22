param(
    [string]$HostName = "phantom.database.local",
    [int]$BackendPort = 8000,
    [switch]$SkipPortProxy,
    [switch]$Elevated
)

$ErrorActionPreference = "Stop"

function Test-IsAdmin {
    $current = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($current)
    return $principal.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
}

function Get-PrimaryIPv4 {
    $candidates = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {
            $_.IPAddress -notlike '127.*' -and
            $_.IPAddress -notlike '169.254*' -and
            $_.PrefixOrigin -ne 'WellKnown'
        }

    if (-not $candidates) {
        throw "No se pudo detectar una IP IPv4 local valida."
    }

    $best = $candidates |
        Sort-Object -Property @{Expression = { $_.SkipAsSource }}, @{Expression = { $_.PrefixLength }} |
        Select-Object -First 1

    return $best.IPAddress
}

function Set-HostsEntry {
    param(
        [string]$HostsPath,
        [string]$Ip,
        [string]$Name
    )

    $content = Get-Content -Path $HostsPath -ErrorAction Stop
    $updated = @()
    $found = $false

    foreach ($line in $content) {
        if ($line -match "(^|\s)$([regex]::Escape($Name))(\s|$)") {
            if (-not $found) {
                $updated += "$Ip`t$Name"
                $found = $true
            }
            continue
        }
        $updated += $line
    }

    if (-not $found) {
        $updated += "$Ip`t$Name"
    }

    Set-Content -Path $HostsPath -Value $updated -Encoding ASCII
}

function Set-PortProxyMapping {
    param(
        [int]$ListenPort,
        [int]$TargetPort
    )

    Start-Service iphlpsvc -ErrorAction SilentlyContinue | Out-Null

    netsh interface portproxy delete v4tov4 listenport=$ListenPort listenaddress=0.0.0.0 | Out-Null
    netsh interface portproxy add v4tov4 listenport=$ListenPort listenaddress=0.0.0.0 connectport=$TargetPort connectaddress=127.0.0.1 | Out-Null

    $ruleName = "DatabaseManager phantom host 80"
    $existingRule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
    if (-not $existingRule) {
        New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort $ListenPort | Out-Null
    }
}

if (-not (Test-IsAdmin)) {
    Write-Host "[INFO] Se requieren permisos de administrador. Solicitando elevacion..." -ForegroundColor Yellow
    $elevationParams = @(
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$PSCommandPath`"",
        "-HostName", "`"$HostName`"",
        "-BackendPort", "$BackendPort",
        "-Elevated"
    )
    if ($SkipPortProxy) {
        $elevationParams += "-SkipPortProxy"
    }

    try {
        $proc = Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList $elevationParams -PassThru
        $proc.WaitForExit()
        exit $proc.ExitCode
    } catch {
        Write-Host "[ERROR] No se pudo elevar el script. Acepta el UAC o ejecuta PowerShell como administrador." -ForegroundColor Red
        exit 1
    }
}

Write-Host "[1/4] Detectando IP local..." -ForegroundColor Cyan
$localIp = Get-PrimaryIPv4
Write-Host "[OK] IP detectada: $localIp" -ForegroundColor Green

Write-Host "[2/4] Actualizando archivo hosts..." -ForegroundColor Cyan
$hostsPath = "$env:SystemRoot\System32\drivers\etc\hosts"
Set-HostsEntry -HostsPath $hostsPath -Ip $localIp -Name $HostName
Write-Host "[OK] Entrada hosts configurada: $HostName -> $localIp" -ForegroundColor Green

Write-Host "[3/4] Limpiando cache DNS..." -ForegroundColor Cyan
ipconfig /flushdns | Out-Null
Write-Host "[OK] Cache DNS limpiada" -ForegroundColor Green

if (-not $SkipPortProxy) {
    Write-Host "[4/4] Configurando acceso sin puerto (80 -> $BackendPort)..." -ForegroundColor Cyan
    Set-PortProxyMapping -ListenPort 80 -TargetPort $BackendPort
    Write-Host "[OK] Port proxy activo: http://$HostName -> http://127.0.0.1:$BackendPort" -ForegroundColor Green
} else {
    Write-Host "[4/4] Omitido: configuracion de port proxy" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Verificacion rapida:" -ForegroundColor Cyan
try {
    $resolved = Resolve-DnsName $HostName -ErrorAction Stop | Select-Object -First 1 -ExpandProperty IPAddress
    Write-Host "- DNS: $HostName -> $resolved" -ForegroundColor Green
} catch {
    Write-Host "- DNS: no se pudo verificar automaticamente" -ForegroundColor Yellow
}

Write-Host "- Prueba URL: http://$HostName" -ForegroundColor Green
Write-Host "- Si el backend aun no esta corriendo, inicia start.bat y vuelve a probar." -ForegroundColor Yellow
