<#
.SYNOPSIS
    Registers Friday's API server as a background task that starts at logon.

.DESCRIPTION
    Creates a "Friday Backend" scheduled task that runs Start-FridayBackend.ps1
    hidden, at logon, with no time limit, so the desktop app always has a
    backend to connect to and never has to reconnect after closing a tab.

    Run from an ordinary PowerShell prompt (no admin needed):
        pwsh -File scripts\windows\Install-FridayService.ps1

.PARAMETER Port
    Port for the API server. Defaults to Friday's own default (8080).

.PARAMETER StartNow
    Also start the task immediately instead of waiting for the next logon.
#>
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

if (-not (Test-Path $runner)) {
    throw "Missing runner script at $runner"
}

$shell = if (Get-Command pwsh -ErrorAction SilentlyContinue) { 'pwsh' } else { 'powershell' }

$arguments = "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$runner`""
if ($FridayHost) { $arguments += " -FridayHost $FridayHost" }
if ($Port -gt 0) { $arguments += " -Port $Port" }

$action = New-ScheduledTaskAction -Execute $shell -Argument $arguments -WorkingDirectory $repoRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -DontStopOnIdleEnd `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

Write-Host "Registered scheduled task '$TaskName'."

if ($StartNow) {
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "Started '$TaskName'. Logs: $(Join-Path $repoRoot 'logs\friday-service.log')"
} else {
    Write-Host "It will start at your next logon. Add -StartNow to start it right away."
}
