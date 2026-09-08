[CmdletBinding()]
param(
    [string]$FridayHost = $env:FRIDAY_HOST,
    [int]$Port = 0
)

$ErrorActionPreference = 'Stop'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$logDir = Join-Path $repoRoot 'logs'
$logFile = Join-Path $logDir 'friday-service.log'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }

function Write-Log([string]$message) {
    "$([DateTime]::Now.ToString('s')) $message" | Add-Content -Path $logFile
}

function Resolve-Python {
    $venv = Join-Path $repoRoot '.venv\Scripts\python.exe'
    if (Test-Path $venv) { return $venv }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) { return $python.Source }
    throw "No Python found. Create $repoRoot\.venv or add python to PATH."
}

$python = Resolve-Python
$server = Join-Path $repoRoot 'desktop\api_server.py'
$serverArgs = @($server)
if ($FridayHost) { $serverArgs += @('--host', $FridayHost) }
if ($Port -gt 0) { $serverArgs += @('--port', $Port) }
Write-Log "starting: $python $($serverArgs -join ' ')"

$delay = 2
$maxDelay = 60
while ($true) {
    $startedAt = Get-Date
    try {
        & $python @serverArgs *>> $logFile
        $exitCode = $LASTEXITCODE
    } catch {
        $exitCode = -1
        Write-Log "launch failed: $($_.Exception.Message)"
    }
    $ranFor = (Get-Date) - $startedAt
    Write-Log "exited with code $exitCode after $([int]$ranFor.TotalSeconds)s; restarting in ${delay}s"
    Start-Sleep -Seconds $delay
    if ($ranFor.TotalSeconds -ge 60) { $delay = 2 } else { $delay = [Math]::Min($delay * 2, $maxDelay) }
}
