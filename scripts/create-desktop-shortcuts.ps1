$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$desktop = [Environment]::GetFolderPath('Desktop')
$wsh = New-Object -ComObject WScript.Shell

function New-Shortcut {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$TargetPath,
        [Parameter(Mandatory = $true)][string]$Arguments,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [string]$Description
    )

    $lnkPath = Join-Path $desktop $Name
    $shortcut = $wsh.CreateShortcut($lnkPath)
    $shortcut.TargetPath = $TargetPath
    $shortcut.Arguments = $Arguments
    $shortcut.WorkingDirectory = $WorkingDirectory
    $shortcut.WindowStyle = 1
    if ($Description) {
        $shortcut.Description = $Description
    }
    $shortcut.IconLocation = "$env:SystemRoot\System32\SHELL32.dll,220"
    $shortcut.Save()
    Write-Host "Creado: $lnkPath"
}

$startScript = Join-Path $root 'start_easy.bat'
$stopScript = Join-Path $root 'stop.bat'

if (-not (Test-Path $startScript)) {
    throw "No existe start_easy.bat en $root"
}
if (-not (Test-Path $stopScript)) {
    throw "No existe stop.bat en $root"
}

New-Shortcut -Name 'Database Manager - Iniciar.lnk' `
    -TargetPath "$env:SystemRoot\System32\cmd.exe" `
    -Arguments "/c `"`"$startScript`"`"" `
    -WorkingDirectory $root `
    -Description 'Inicia Database Manager y abre la interfaz automáticamente.'

New-Shortcut -Name 'Database Manager - Detener.lnk' `
    -TargetPath "$env:SystemRoot\System32\cmd.exe" `
    -Arguments "/c `"`"$stopScript`"`"" `
    -WorkingDirectory $root `
    -Description 'Detiene el servidor de Database Manager.'

Write-Host 'Accesos directos listos en el escritorio.'
