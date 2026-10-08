[CmdletBinding()]
param(
    [string]$ConfigPath = (Join-Path $PSScriptRoot 'profiles.json'),
    [string]$At = '03:00',
    [string]$TaskName = 'SaveHarbor Pro Daily Backups'
)

$ErrorActionPreference = 'Stop'
$runner = Join-Path $PSScriptRoot 'Run-SaveHarborBackups.ps1'
if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) { throw "Runner script not found: $runner" }
if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) { throw "Configuration file not found: $ConfigPath" }

$powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$arguments = '-NoProfile -ExecutionPolicy RemoteSigned -File "{0}" -ConfigPath "{1}"' -f $runner, $ConfigPath
$action = New-ScheduledTaskAction -Execute $powershell -Argument $arguments -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
$task = New-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'Creates and verifies local SaveHarbor snapshots, then applies the configured retention limit.'
Register-ScheduledTask -TaskName $TaskName -InputObject $task -Force | Out-Null
Write-Host "Registered '$TaskName' for daily execution at $At (current user; no elevated privileges)."
Write-Host 'Run it once from Task Scheduler or execute Run-SaveHarborBackups.ps1 manually to confirm your profile paths.'
