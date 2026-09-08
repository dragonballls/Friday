# Always-on Friday

Friday's UI connects to the local API server. On Windows, the bundled service runner keeps that server alive across terminal closure, reloads, and ordinary crashes.

## Windows

From the Friday repository:

```powershell
pwsh -File scripts\windows\Install-FridayService.ps1 -StartNow
```

The installer creates a per-user Scheduled Task, so administrator access is not required. The runner prefers `.venv\Scripts\python.exe` and restarts the API with exponential backoff if it exits.

Logs are written to `logs\friday-service.log`.

Remove the task with:

```powershell
pwsh -File scripts\windows\Uninstall-FridayService.ps1
```

The service cannot run while Windows itself is powered off or asleep.

## Browser/app freshness

Production builds watch `index.html` for changed hashed JavaScript/CSS assets. An already-open browser tab checks periodically, when it becomes visible, and when the network returns. A changed build is loaded automatically. Development remains under Vite HMR.
