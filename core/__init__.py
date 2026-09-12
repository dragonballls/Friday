"""Core package bootstrap.

Starts the bounded autonomous coding service once the desktop API process is up.
The service is deliberately isolated and will no-op if its persistent workspace
cannot be established.
"""

from __future__ import annotations

import os
import threading
import time


_started = False
_started_lock = threading.Lock()


def _start_autonomous_service() -> None:
    global _started
    if os.getenv("FRIDAY_DISABLE_AUTONOMOUS", "").strip().lower() in {"1", "true", "yes", "on"}:
        return
    with _started_lock:
        if _started:
            return
        _started = True

    def runner() -> None:
        time.sleep(8)
        try:
            from core.autonomous_service import run_forever

            run_forever()
        except Exception:
            # Never let the background service affect normal Friday startup.
            pass

    threading.Thread(target=runner, name="FridayAutonomousCoder", daemon=True).start()


_start_autonomous_service()
