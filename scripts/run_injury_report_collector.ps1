<#
.SYNOPSIS
    Collect, parse, and reconcile official NBA injury reports with bounded catch-up.

.DESCRIPTION
    Requires YUNOBALL_INJURY_REPORT_ARCHIVE_DIR to point outside the repository.
    The shared daily lock covers collection/parsing and is reacquired for exact
    identity reconciliation. Any failed phase or unresolved identity returns non-zero.

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

    [string]$Season,

    [ValidateRange(1, 5000)]
    [int]$ParseMaxDocuments = 1000,

    [ValidateSet('Direct', 'Configured')]
    [string]$NetworkMode = 'Direct'
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot 'venv\Scripts\python.exe'
$Pipeline = Join-Path $PSScriptRoot 'run_official_injury_pipeline.py'

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Project virtualenv Python was not found: $Python"
}
if (-not (Test-Path -LiteralPath $Pipeline -PathType Leaf)) {
    throw "Official injury-report pipeline was not found: $Pipeline"
}
if ([string]::IsNullOrWhiteSpace($ArchiveRoot)) {
    throw 'Set YUNOBALL_INJURY_REPORT_ARCHIVE_DIR or pass -ArchiveRoot before scheduling collection.'
}

$env:YUNOBALL_INJURY_REPORT_ARCHIVE_DIR = $ArchiveRoot
if ($NetworkMode -eq 'Direct') {
    # This Windows wrapper is the personal-PC entry point. Prefer the verified
    # local route; retain an explicit opt-in to environment/proxy policy.
    $env:FORCE_LOCAL = 'true'
    $env:FORCE_PROXY = 'false'
    $env:PROXY_ENABLED = 'false'
}
$Arguments = @(
    $Pipeline,
    '--archive-root', $ArchiveRoot,
    '--retry-interval-hours', $RetryIntervalHours,
    '--freshness-threshold-hours', $FreshnessThresholdHours,
    '--lookback-days', $LookbackDays,
    '--parse-max-documents', $ParseMaxDocuments
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
