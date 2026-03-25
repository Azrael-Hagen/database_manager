Param(
    [int]$Weeks = 12,
    [string]$FromDate = "",
    [string]$ToDate = "",
    [int]$AgentId = 0,
    [ValidateSet("csv", "json", "both")]
    [string]$OutputFormat = "both"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$env:PYTHONPATH = "backend"

$argsList = @("backend/scripts/generar_reporte_conciliacion.py", "--weeks", "$Weeks", "--output-format", $OutputFormat)

if ($FromDate -ne "") {
    $argsList += @("--from-date", $FromDate)
}

if ($ToDate -ne "") {
    $argsList += @("--to-date", $ToDate)
}

if ($AgentId -gt 0) {
    $argsList += @("--agent-id", "$AgentId")
}

python @argsList
