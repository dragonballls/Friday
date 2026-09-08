[CmdletBinding()]
param(
    [switch]$StartNow
)

$ErrorActionPreference = 'Stop'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$syncScript = Join-Path $repoRoot 'scripts\windows\Sync-Friday.ps1'
$taskName = 'Friday GitHub Sync'

if (-not (Test-Path $syncScript)) { throw "Missing $syncScript" }

$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$syncScript`""
$logonTrigger = New-ScheduledTaskTrigger -AtLogOn
$intervalTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 2) -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger @($logonTrigger,$intervalTrigger) -Settings $settings -Principal $principal -Description 'Keeps the local Friday checkout synchronized with GitHub main without overwriting tracked local edits.' | Out-Null

if ($StartNow) { Start-ScheduledTask -TaskName $taskName }
Write-Host "Installed: $taskName"
Write-Host "Repository: $repoRoot"
Write-Host "Schedule: at logon and every 2 minutes"
