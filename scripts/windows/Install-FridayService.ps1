[CmdletBinding()]
param(
    [string]$TaskName = 'Friday Backend',
    [string]$FridayHost = '',
    [int]$Port = 0,
    [switch]$StartNow
)

$ErrorActionPreference = 'Stop'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$runner = Join-Path $repoRoot 'scripts\windows\Start-FridayBackend.ps1'
if (-not (Test-Path $runner)) { throw "Missing runner script at $runner" }

$shell = if (Get-Command pwsh -ErrorAction SilentlyContinue) { 'pwsh' } else { 'powershell' }
$arguments = "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$runner`""
if ($FridayHost) { $arguments += " -FridayHost $FridayHost" }
if ($Port -gt 0) { $arguments += " -Port $Port" }

$action = New-ScheduledTaskAction -Execute $shell -Argument $arguments -WorkingDirectory $repoRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -DontStopOnIdleEnd -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Host "Registered scheduled task '$TaskName'."
if ($StartNow) {
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "Started '$TaskName'."
} else {
    Write-Host "It will start at your next logon. Use -StartNow to start it now."
}
