<#
.SYNOPSIS
    Windows Task Scheduler entry point for the NBA daily ingest pipeline.

.DESCRIPTION
    Activates the project venv, runs daily_ingest.py (fetch + calc + validate),
    and exits with the pipeline exit code.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\run_daily_ingest.ps1
    powershell -ExecutionPolicy Bypass -File scripts\run_daily_ingest.ps1 -Proxy
    powershell -ExecutionPolicy Bypass -File scripts\run_daily_ingest.ps1 -Local
#>

param(
    [switch]$Proxy,
    [switch]$Local,
    [switch]$SkipValidate,
    [string]$Season = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$VenvPython = Join-Path $ProjectRoot "venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Error "Virtualenv python not found at $VenvPython. Activate/create venv first."
    exit 1
}

$Args = @("daily_ingest.py")
if ($Proxy) { $Args += "--proxy" }
if ($Local) { $Args += "--local" }
if ($SkipValidate) { $Args += "--skip-validate" }
if ($Season) { $Args += @("--season", $Season) }

if ($Local -and -not $Proxy) {
    Write-Host "Local mode: sequential API calls (MAX_WORKERS=1). Prefer -Proxy for daily runs."
}

Write-Host "Running: $VenvPython $($Args -join ' ')"
& $VenvPython @Args
$exitCode = $LASTEXITCODE

$marker = Join-Path $ProjectRoot "data\last_ingest_success.json"
if (Test-Path $marker) {
    Write-Host "Last success marker: $marker"
    Get-Content $marker
}

exit $exitCode
