[CmdletBinding()]
param(
    [switch]$Force,
    [switch]$Daemon
)

$ErrorActionPreference = 'Stop'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$logDir = Join-Path $repoRoot 'logs'
$logFile = Join-Path $logDir 'friday-sync.log'
$lockFile = Join-Path $repoRoot '.friday\github-sync.lock'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
if (-not (Test-Path (Split-Path $lockFile))) { New-Item -ItemType Directory -Path (Split-Path $lockFile) -Force | Out-Null }

function Write-Log([string]$Message) {
    "$([DateTime]::Now.ToString('s')) $Message" | Add-Content -Path $logFile
}

function Invoke-Sync {
    $mutex = New-Object System.Threading.Mutex($false, 'Friday-GitHub-Sync')
    try {
        if (-not $mutex.WaitOne(0)) { Write-Log 'another sync is already running; exiting'; return }

        Set-Location $repoRoot
        $branch = (& git branch --show-current).Trim()
        if ($branch -ne 'main') {
            Write-Log "skipping: local branch is '$branch', expected 'main'"
            return
        }

        if (-not $Force) {
            & git diff --quiet
            if ($LASTEXITCODE -ne 0) { Write-Log 'skipping: tracked working-tree changes detected'; return }
            & git diff --cached --quiet
            if ($LASTEXITCODE -ne 0) { Write-Log 'skipping: staged changes detected'; return }
        }

        & git fetch --prune origin main
        if ($LASTEXITCODE -ne 0) { throw 'git fetch failed' }

        $local = (& git rev-parse HEAD).Trim()
        $remote = (& git rev-parse origin/main).Trim()
        if ($local -eq $remote) { return }

        $changed = @(git diff --name-only "$local..$remote")
        Write-Log "updating $local -> $remote ($($changed.Count) files)"

        & git merge --ff-only origin/main
        if ($LASTEXITCODE -ne 0) { throw 'fast-forward failed' }

        $frontendChanged = $changed | Where-Object { $_ -like 'desktop/*' }
        $backendChanged = $changed | Where-Object { $_ -like '*.py' -or $_ -like 'requirements*.txt' -or $_ -like 'config/*' }
        $packageChanged = $changed | Where-Object { $_ -eq 'desktop/package.json' -or $_ -eq 'desktop/package-lock.json' }

        if ($frontendChanged) {
            Set-Location (Join-Path $repoRoot 'desktop')
            if ($packageChanged) {
                Write-Log 'frontend dependency files changed; running npm ci'
                & npm ci *>> $logFile
                if ($LASTEXITCODE -ne 0) { throw 'npm ci failed' }
            }
            Write-Log 'building frontend'
            & npm run build *>> $logFile
            if ($LASTEXITCODE -ne 0) { throw 'frontend build failed' }
            Set-Location $repoRoot

            $vite = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
            if ($vite) {
                Write-Log "restarting Vite PID $($vite[0].OwningProcess)"
                Stop-Process -Id $vite[0].OwningProcess -Force -ErrorAction SilentlyContinue
                Start-Sleep -Seconds 2
            }
            $desktop = Join-Path $repoRoot 'desktop'
            Start-Process powershell.exe -WindowStyle Hidden -ArgumentList '-NoProfile','-Command',"Set-Location '$desktop'; npm run dev -- --host 127.0.0.1 --port 5173 --strictPort"
        }

        if ($backendChanged) {
            Write-Log 'backend-related files changed; restarting backend task if installed'
            $task = Get-ScheduledTask -TaskName 'Friday Backend' -ErrorAction SilentlyContinue
            if ($task) { Restart-ScheduledTask -TaskName 'Friday Backend' }
        }

        Write-Log "update complete: $remote"
    }
    catch {
        Write-Log "ERROR: $($_.Exception.Message)"
    }
    finally {
        try { $mutex.ReleaseMutex() | Out-Null } catch {}
        $mutex.Dispose()
    }
}

if ($Daemon) {
    Write-Log 'sync daemon started (10-second polling)'
    while ($true) {
        Invoke-Sync
        Start-Sleep -Seconds 10
    }
}
else {
    Invoke-Sync
}
