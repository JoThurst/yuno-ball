<# Run a bounded historical official NBA injury-report filename scan. #>

[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$StartDate,
    [Parameter(Mandatory)] [string]$EndDate,
    [ValidateSet(15, 30, 60)] [int]$IntervalMinutes = 15,
    [ValidateRange(5, 120)] [int]$TimeoutSeconds = 5,
    [ValidateSet(0, 1)] [int]$CurlRetries = 0,
    [ValidateRange(1, 31)] [int]$MaxDates = 7,
    [string]$StartTime = '12:00',
    [string]$EndTime = '23:45',
    [string]$ArchiveRoot = $env:YUNOBALL_INJURY_REPORT_ARCHIVE_DIR,
    [string]$Season,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot 'venv\Scripts\python.exe'
$Backfill = Join-Path $PSScriptRoot 'backfill_official_injury_reports.py'

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Project virtualenv Python was not found: $Python"
}
if (-not (Test-Path -LiteralPath $Backfill -PathType Leaf)) {
    throw "Official injury-report backfill was not found: $Backfill"
}
if (-not $DryRun -and [string]::IsNullOrWhiteSpace($ArchiveRoot)) {
    throw 'Set YUNOBALL_INJURY_REPORT_ARCHIVE_DIR or pass -ArchiveRoot.'
}

$Arguments = @(
    $Backfill,
    '--start-date', $StartDate,
    '--end-date', $EndDate,
    '--start-time', $StartTime,
    '--end-time', $EndTime,
    '--interval-minutes', $IntervalMinutes,
    '--max-dates', $MaxDates,
    '--timeout-seconds', $TimeoutSeconds,
    '--curl-retries', $CurlRetries
)
$Arguments += if ($DryRun) { '--dry-run' } else { '--apply' }
if ($ArchiveRoot) { $Arguments += @('--archive-root', $ArchiveRoot) }
if ($Season) { $Arguments += @('--season', $Season) }

Push-Location $ProjectRoot
try {
    & $Python @Arguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
