[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ArchiveRoot,
    [string]$StateDir = (Join-Path $env:LOCALAPPDATA 'YunoBall\operations'),
    [string]$PgBin = 'C:\Program Files\PostgreSQL\17\bin',
    [switch]$CheckOnly,
    [switch]$Force
)
$ErrorActionPreference = 'Stop'
if ((Get-TimeZone).Id -ne 'Eastern Standard Time') {
    throw 'Scheduled PC runs require Windows Eastern Standard Time; correct the timezone before running.'
}
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot 'venv\Scripts\python.exe'
$cycleScript = Join-Path $PSScriptRoot 'run_local_ingestion_cycle.py'
if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) { throw 'Project Python is missing.' }
New-Item -ItemType Directory -Path $StateDir -Force | Out-Null
$logPath = Join-Path $StateDir ('cycle-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff') + '-' + $PID + '.log')
$cycleArgs = @($cycleScript, '--archive-root', $ArchiveRoot, '--state-dir', $StateDir, '--pg-bin', $PgBin)
if ($CheckOnly) { $cycleArgs += '--check-only' }
if ($Force) { $cycleArgs += '--force' }
Push-Location $projectRoot
try {
    # Preserve Python's exit code: progress on native stderr is not failure.
    $ErrorActionPreference = 'Continue'
    & $pythonPath @cycleArgs *> $logPath
    $cycleExit = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    Write-Host "YunoBall cycle exit=$cycleExit log=$logPath"
    exit $cycleExit
} finally { Pop-Location }
