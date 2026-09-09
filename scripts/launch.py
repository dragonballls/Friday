#!/usr/bin/env python3
"""Start Friday safely, with fast desktop startup and crash recovery.

The normal CLI path applies the safe source updater first. The desktop path
starts immediately and relies on the UI supervisor's background update monitor,
with an outer recovery loop for supervisor crashes.
"""

from __future__ import annotations

import datetime as _dt
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UPDATER = ROOT / "scripts" / "update.py"
MAIN = ROOT / "main.py"
LOG_DIR = ROOT / "logs"
LAUNCH_LOG = LOG_DIR / "launcher.log"


def _log(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().astimezone().isoformat(timespec="seconds")
    with LAUNCH_LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"[{stamp}] {message}\n")
    print(message, file=sys.stderr)


def _run_update() -> None:
    """Run the normal safe updater without making failures fatal."""
    result = subprocess.run([sys.executable, str(UPDATER)], cwd=ROOT, check=False)
    if result.returncode not in (0, 2, 3, 4):
        _log(f"Friday update failed (code {result.returncode}); launching current checkout.")


def main() -> int:
    args = sys.argv[1:]

    # Desktop startup must never wait for a Git/network operation. The UI's own
    # updater can check for updates after the services are already responsive.
    if "--ui" not in args:
        _run_update()

    if "--ui" not in args:
        return subprocess.run([sys.executable, str(MAIN), *args], cwd=ROOT, check=False).returncode

    # If the supervisor itself crashes before it can recover its child services,
    # keep the desktop launcher alive and restart it. This is intentionally a
    # last-resort outer guard; normal service recovery remains inside main.py.
    attempt = 0
    while True:
        attempt += 1
        _log(f"Starting Friday desktop supervisor (attempt {attempt}).")
        try:
            result = subprocess.run([sys.executable, str(MAIN), *args], cwd=ROOT, check=False)
        except KeyboardInterrupt:
            _log("Friday desktop launcher stopped by user.")
            return 0

        if result.returncode == 0:
            _log("Friday desktop supervisor exited normally.")
            return 0

        _log(f"Friday desktop supervisor exited with code {result.returncode}; retrying in 2 seconds.")
        try:
            time.sleep(2.0)
        except KeyboardInterrupt:
            _log("Friday desktop launcher stopped by user.")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
