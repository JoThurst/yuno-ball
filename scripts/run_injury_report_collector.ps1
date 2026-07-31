<#
.SYNOPSIS
    Run official NBA injury-report discovery with bounded recent-date catch-up.

.DESCRIPTION
    Requires YUNOBALL_INJURY_REPORT_ARCHIVE_DIR to point outside the repository.
    The collector's non-zero exit code is preserved so Task Scheduler can record
    partial/failing runs for review.

.EXAMPLE
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File \
      C:\Code\sports_analytics\scripts\run_injury_report_collector.ps1
#>

[CmdletBinding()]
param(
    [ValidateRange(1, 24)]
    [int]$RetryIntervalHours = 2,

    [ValidateRange(1, 48)]
    [int]$FreshnessThresholdHours = 4,

    [ValidateRange(0, 7)]
    [int]$LookbackDays = 7,

    [string]$ArchiveRoot = $env:YUNOBALL_INJURY_REPORT_ARCHIVE_DIR,

    [string]$ReportDate,

    [string]$Season
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot 'venv\Scripts\python.exe'
$Collector = Join-Path $PSScriptRoot 'collect_official_injury_reports.py'

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Project virtualenv Python was not found: $Python"
}
if (-not (Test-Path -LiteralPath $Collector -PathType Leaf)) {
    throw "Official injury-report collector was not found: $Collector"
}
if ([string]::IsNullOrWhiteSpace($ArchiveRoot)) {
    throw 'Set YUNOBALL_INJURY_REPORT_ARCHIVE_DIR or pass -ArchiveRoot before scheduling collection.'
}

$env:YUNOBALL_INJURY_REPORT_ARCHIVE_DIR = $ArchiveRoot
$Arguments = @(
    $Collector,
    '--apply',
    '--retry-interval-hours', $RetryIntervalHours,
    '--freshness-threshold-hours', $FreshnessThresholdHours,
    '--lookback-days', $LookbackDays
)
if ($ReportDate) {
    $Arguments += @('--report-date', $ReportDate)
}
if ($Season) {
    $Arguments += @('--season', $Season)
}

Push-Location $ProjectRoot
try {
    & $Python @Arguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
