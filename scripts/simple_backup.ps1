# Simple backup script for YunoBall database
$backupBase = Join-Path $env:LOCALAPPDATA "YunoBall\backups"
$scriptsDir = Join-Path $backupBase "scripts"

# Create backup directories if they don't exist
$dirs = @("daily", "weekly", "monthly", "scripts")
foreach ($dir in $dirs) {
    $path = Join-Path $backupBase $dir
    New-Item -ItemType Directory -Path $path -Force | Out-Null
}

# Get database URL from .env file
$env:DATABASE_URL = python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('DATABASE_URL'))"

# Create backup tasks
$tasks = @(
    @{Name="YunoBall Daily Backup"; Schedule="DAILY"; Time="00:00"}
    @{Name="YunoBall Weekly Backup"; Schedule="WEEKLY"; Time="01:00"; Day="SUN"}
    @{Name="YunoBall Monthly Backup"; Schedule="ONCE"; Time="02:00"}
)

# Remove existing tasks
Get-ScheduledTask | Where-Object {$_.TaskName -like "*YunoBall*"} | Unregister-ScheduledTask -Confirm:$false

foreach ($task in $tasks) {
    # Create batch file for this task
    $batchFile = Join-Path $scriptsDir "$($task.Schedule.ToLower())_backup.bat"
    $backupCmd = "@echo off`r`ncd $((Get-Location).Path)`r`nset DATABASE_URL=$env:DATABASE_URL`r`npg_dump --dbname=`"%DATABASE_URL%`" --format=custom --file=`"$backupBase\$($task.Schedule.ToLower())\yunoball_$($task.Schedule.ToLower())_%date:~-4,4%%date:~-10,2%%date:~-7,2%.sql`""
    Set-Content -Path $batchFile -Value $backupCmd
    
    switch ($task.Schedule) {
        "DAILY" { 
            schtasks /create /tn $task.Name /tr $batchFile /sc DAILY /st $task.Time /ru "$env:USERDOMAIN\$env:USERNAME" /f
        }
        "WEEKLY" { 
            schtasks /create /tn $task.Name /tr $batchFile /sc WEEKLY /d $task.Day /st $task.Time /ru "$env:USERDOMAIN\$env:USERNAME" /f
        }
        "ONCE" { 
            # For monthly, we'll create it to run on the 1st of next month
            $nextMonth = (Get-Date).AddMonths(1).ToString("MM/01/yyyy")
            schtasks /create /tn $task.Name /tr $batchFile /sc MONTHLY /d 1 /st $task.Time /sd $nextMonth /ru "$env:USERDOMAIN\$env:USERNAME" /f
        }
    }
    Write-Host "Created task: $($task.Name)"
}

# Test backup
Write-Host "`nTesting backup..."
$testFile = Join-Path $backupBase "test_$(Get-Date -Format 'yyyyMMdd_HHmmss').sql"
pg_dump --dbname="$env:DATABASE_URL" --format=custom --file="$testFile"

if (Test-Path $testFile) {
    Write-Host "Backup test successful! Created: $testFile"
    Remove-Item $testFile
} else {
    Write-Host "Backup test failed!"
} 