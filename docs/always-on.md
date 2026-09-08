# Always-on Friday

Friday's UI talks to the API server over SSE. If the server only runs while a
terminal is open, closing that terminal (or reloading the page before the
server is back) shows "Backend offline" / "Reconnecting…". Running the server
as a background task removes that entirely: the UI reconnects instantly on
every reload because the backend never went away.

## Windows

Install (no admin required — it registers a per-user scheduled task):

```powershell
pwsh -File scripts\windows\Install-FridayService.ps1 -StartNow
```

Options:

| Flag | Meaning |
| --- | --- |
| `-StartNow` | Start immediately instead of waiting for the next logon |
| `-Port 9000` | Bind a different port (default 8080) |
| `-FridayHost 0.0.0.0` | Bind a different interface, e.g. to reach Friday from your phone on the same LAN |
| `-TaskName "..."` | Use a different scheduled task name |

The task runs `scripts\windows\Start-FridayBackend.ps1` hidden, with no
execution time limit, and that script relaunches the server (with backoff) if
it ever exits — so a crash self-heals.

Check on it:

```powershell
Get-ScheduledTask -TaskName 'Friday Backend'
Get-Content logs\friday-service.log -Tail 50 -Wait
```

Remove it:

```powershell
pwsh -File scripts\windows\Uninstall-FridayService.ps1
```

The script prefers `.venv\Scripts\python.exe` in the repository root and falls
back to `python` on `PATH`.

## macOS / Linux

There is no bundled unit yet; a minimal systemd user service does the same job:

```ini
# ~/.config/systemd/user/friday.service
[Unit]
Description=Friday API server

[Service]
WorkingDirectory=%h/Friday
ExecStart=%h/Friday/.venv/bin/python desktop/api_server.py
Restart=always

[Install]
WantedBy=default.target
```

```bash
systemctl --user enable --now friday
loginctl enable-linger "$USER"   # keep it running after you log out
```

## What this does not do

The backend still runs on your machine, so it stops when the machine is off or
asleep. Reaching Friday while the computer is off requires hosting the backend
somewhere else, which is a separate (and not free) setup.
