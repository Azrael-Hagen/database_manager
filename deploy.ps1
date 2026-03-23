param(
    [ValidateSet("deploy", "status", "switch")]
    [string]$Action = "deploy",
    [ValidateSet("blue", "green")]
    [string]$Color,
    [switch]$SkipBuild,
    [switch]$NoRollback,
    [int]$MaxAttempts = 40,
    [int]$WaitSeconds = 2
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$scriptParams = @{
    Action = $Action
    ComposeFile = "docker-compose.bluegreen.yml"
    ActiveFile = "deploy/active-upstream.conf"
    MaxAttempts = $MaxAttempts
    WaitSeconds = $WaitSeconds
}

if ($PSBoundParameters.ContainsKey("Color")) {
    $scriptParams.Color = $Color
}
if ($SkipBuild) {
    $scriptParams.SkipBuild = $true
}
if ($NoRollback) {
    $scriptParams.NoRollback = $true
}

& "$ProjectRoot\scripts\deploy-bluegreen.ps1" @scriptParams
exit $LASTEXITCODE
