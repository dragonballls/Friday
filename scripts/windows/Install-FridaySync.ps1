[CmdletBinding()]
param(
    [switch]$StartNow
)

$ErrorActionPreference = 'Stop'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$syncScript = Join-Path $repoRoot 'scripts\windows\Sync-Friday.ps1'
$runName = 'Friday GitHub Sync'
$runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'

if (-not (Test-Path $syncScript)) { throw "Missing $syncScript" }

# Task Scheduler can be blocked by local Windows policy even for per-user tasks.
# HKCU\Run is user-scoped and requires no administrator rights, so use it as the
# durable mechanism for the sync daemon.
$command = "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$syncScript`" -Daemon"
New-Item -Path $runKey -Force | Out-Null
Set-ItemProperty -Path $runKey -Name $runName -Value $command

if ($StartNow) {
    Start-Process powershell.exe -WindowStyle Hidden -ArgumentList '-NoProfile','-WindowStyle','Hidden','-ExecutionPolicy','Bypass','-File',"$syncScript",'-Daemon'
}

Write-Host "Installed: $runName"
Write-Host "Repository: $repoRoot"
Write-Host "Schedule: at Windows logon and every 2 minutes while signed in"
