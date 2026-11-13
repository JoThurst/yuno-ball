<# Install only the named YunoBall local ingestion tasks; preserve other tasks. #>
[CmdletBinding(SupportsShouldProcess=$true)]
param([Parameter(Mandatory=$true)][string]$ArchiveRoot)
$ErrorActionPreference = 'Stop'
if ((Get-TimeZone).Id -ne 'Eastern Standard Time') { throw 'Set Windows to Eastern Time before installing.' }
if (-not (Test-Path -LiteralPath $ArchiveRoot -PathType Container)) { throw 'ArchiveRoot must exist.' }
$projectRoot = Split-Path -Parent $PSScriptRoot
$shellPath = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
$wrapperPath = Join-Path $PSScriptRoot 'run_local_ingestion_cycle.ps1'
if ($ArchiveRoot.Contains('"')) { throw 'Invalid quote in archive path' }
$actionArgs = '-NoProfile -ExecutionPolicy Bypass -File "' + $wrapperPath + '" -ArchiveRoot "' + $ArchiveRoot + '"'
$action = New-ScheduledTaskAction -Execute $shellPath -Argument $actionArgs -WorkingDirectory $projectRoot
$userId = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
# Interactive token avoids writing a password into scripts. Locked/sleeping
# signed-in sessions can run; signed-out operation needs a later credential setup.
$principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3) -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 15) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$triggers = @((New-ScheduledTaskTrigger -Daily -At '08:00'), (New-ScheduledTaskTrigger -Daily -At '09:30'))
# Floating local wall times follow the validated Windows Eastern timezone and
# DST. A fixed -04:00 boundary would bind the schedule to summer UTC offset.
$boundaryDate = (Get-Date).ToString('yyyy-MM-dd')
$triggers[0].StartBoundary = $boundaryDate + 'T08:00:00'
$triggers[1].StartBoundary = $boundaryDate + 'T09:30:00'
if ($PSCmdlet.ShouldProcess('YunoBall Morning Ingestion', 'Register 08:00 and 09:30 Eastern task')) {
    Register-ScheduledTask -TaskName 'YunoBall Morning Ingestion' -Action $action -Trigger $triggers `
        -Principal $principal -Settings $settings -Description 'Validated once-per-Eastern-date local ingestion with backup and source catch-up.' -Force | Out-Null
}
$availabilitySettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$hourly = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) -RepetitionInterval (New-TimeSpan -Hours 1)
$logon = New-ScheduledTaskTrigger -AtLogOn -User $userId
if ($PSCmdlet.ShouldProcess('YunoBall Availability Catchup', 'Register hourly and logon catch-up without wake')) {
    Register-ScheduledTask -TaskName 'YunoBall Availability Catchup' -Action $action -Trigger @($hourly, $logon) `
        -Principal $principal -Settings $availabilitySettings -Description 'Refreshes availability hourly or at sign-in after 08:00 Eastern; reuses successful daily stats and backup.' -Force | Out-Null
}
Write-Host 'Configured 08:00 and 09:30 Eastern, failed-run retries, and hourly/sign-in catch-up. Remain signed in; locking the screen is fine.'
if (-not $WhatIfPreference) {
    # Daily backups now belong to the cycle's credential-safe backup gate.
    # Retain exact old definitions and files; never unregister wildcard tasks.
    $taskBackupDir = Join-Path $env:LOCALAPPDATA 'YunoBall\operations\previous-tasks'
    New-Item -ItemType Directory -Path $taskBackupDir -Force | Out-Null
    foreach ($oldName in @('YunoBall Daily Backup', 'YunoBall Weekly Backup', 'YunoBall Monthly Backup')) {
        $oldTask = Get-ScheduledTask -TaskName $oldName -ErrorAction SilentlyContinue
        if ($oldTask -and $oldTask.State -ne 'Disabled' -and $PSCmdlet.ShouldProcess($oldName, 'Disable failed legacy backup task; retain definition')) {
            $savedTaskPath = Join-Path $taskBackupDir ($oldName.Replace(' ', '-') + '.xml')
            if (-not (Test-Path -LiteralPath $savedTaskPath)) { Export-ScheduledTask -TaskName $oldName | Set-Content -LiteralPath $savedTaskPath }
            Disable-ScheduledTask -TaskName $oldName | Out-Null
        }
    }
}
