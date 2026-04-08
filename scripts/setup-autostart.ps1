param(
    [ValidateSet("install", "remove", "status")]
    [string]$Action = "status",
    [ValidateSet("logon", "startup")]
    [string]$Mode = "logon",
    [string]$TaskName = "DatabaseManager_Autostart",
    [int]$DelaySeconds = 20
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$StartScript = Join-Path $ProjectRoot "start_easy.bat"

function Write-Info([string]$msg) {
    Write-Host "[INFO] $msg" -ForegroundColor Cyan
}

function Write-Ok([string]$msg) {
    Write-Host "[OK] $msg" -ForegroundColor Green
}

function Write-Warn([string]$msg) {
    Write-Host "[WARN] $msg" -ForegroundColor Yellow
}

function Get-TaskSafe {
    try {
        return Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    } catch {
        return $null
    }
}

if (-not (Test-Path $StartScript)) {
    throw "No se encontró $StartScript"
}

switch ($Action) {
    "status" {
        $task = Get-TaskSafe
        if (-not $task) {
            Write-Warn "No existe la tarea '$TaskName'."
            exit 0
        }
        $info = Get-ScheduledTaskInfo -TaskName $TaskName
        Write-Ok "Tarea encontrada: $TaskName"
        Write-Host "  Estado   : $($task.State)"
        Write-Host "  Trigger  : $($task.Triggers[0].CimClass.CimClassName)"
        Write-Host "  Última ejecución : $($info.LastRunTime)"
        Write-Host "  Último resultado : $($info.LastTaskResult)"
        exit 0
    }

    "remove" {
        $task = Get-TaskSafe
        if (-not $task) {
            Write-Warn "No hay tarea para eliminar: '$TaskName'."
            exit 0
        }
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Ok "Autoinicio eliminado correctamente."
        exit 0
    }

    "install" {
        Write-Info "Configurando autoinicio ($Mode)..."

        $existing = Get-TaskSafe
        if ($existing) {
            Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        }

        $cmd = "`"$StartScript`" --reuse"
        $actionObj = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c $cmd" -WorkingDirectory "$ProjectRoot"

        if ($Mode -eq "startup") {
            $trigger = New-ScheduledTaskTrigger -AtStartup
            $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
        } else {
            $currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
            $trigger = New-ScheduledTaskTrigger -AtLogOn -User $currentUser
            $principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType Interactive -RunLevel Limited
        }

        if ($DelaySeconds -gt 0) {
            $trigger.Delay = "PT${DelaySeconds}S"
        }

        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

        Register-ScheduledTask `
            -TaskName $TaskName `
            -Action $actionObj `
            -Trigger $trigger `
            -Principal $principal `
            -Settings $settings `
            -Description "Inicia Database Manager automáticamente al iniciar sesión/sistema" `
            | Out-Null

        Write-Ok "Autoinicio configurado correctamente."
        Write-Host "  Tarea : $TaskName"
        Write-Host "  Modo  : $Mode"
        Write-Host "  Script: $StartScript"
        exit 0
    }
}
