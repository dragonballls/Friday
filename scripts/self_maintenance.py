from __future__ import annotations

import os
import threading
from typing import Any

from core.github_self_maintenance import GitHubSelfMaintenance, GitHubSelfMaintenanceError


DEFAULT_INTERVAL = 300


class ContinuousSelfMaintenance:
    """Continuously watch Friday's GitHub state and repair safe opportunities.

    The worker is intentionally conservative: it only becomes active when a
    GitHub token is configured, never writes directly to main, and relies on
    GitHubSelfMaintenance for path/secret/workflow safety and PR creation.
    """

    def __init__(self, interval: int | None = None) -> None:
        self.interval = max(60, int(interval or os.environ.get("FRIDAY_SELF_MAINTENANCE_INTERVAL", DEFAULT_INTERVAL)))
        self.enabled = os.environ.get("FRIDAY_GITHUB_AUTOFIX", "1") == "1"
        self.controller = GitHubSelfMaintenance()
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.last_result: dict[str, Any] = {"status": "not_started"}
        self._active = threading.Lock()

    @property
    def configured(self) -> bool:
        return self.enabled and self.controller.configured

    def start(self) -> bool:
        if not self.configured or self.thread is not None and self.thread.is_alive():
            return False
        self.thread = threading.Thread(
            target=self._run,
            name="friday-self-maintenance",
            daemon=True,
        )
        self.thread.start()
        return True

    def stop(self) -> None:
        self.stop_event.set()

    def run_once(self) -> dict[str, Any]:
        if not self.configured:
            self.last_result = {
                "status": "disabled",
                "reason": "GitHub token/configuration is unavailable",
            }
            return self.last_result
        if not self._active.acquire(blocking=False):
            return {"status": "busy"}
        try:
            failure = self.controller.latest_failed_run()
            if failure is None:
                self.last_result = {
                    "status": "healthy",
                    "message": "No failed main-branch workflow detected.",
                }
                return self.last_result

            result = self.controller.repair_latest_failure(apply=True, max_files=3)
            self.last_result = {
                "status": "repair_proposed",
                "failure": {
                    "id": failure.get("id"),
                    "name": failure.get("name"),
                    "head_sha": failure.get("head_sha"),
                    "html_url": failure.get("html_url"),
                },
                "result": result,
            }
            return self.last_result
        except (GitHubSelfMaintenanceError, OSError, ValueError) as exc:
            self.last_result = {"status": "error", "error": str(exc)}
            return self.last_result
        finally:
            self._active.release()

    def _run(self) -> None:
        self.last_result = {"status": "running", "interval_seconds": self.interval}
        while not self.stop_event.is_set():
            self.run_once()
            self.stop_event.wait(self.interval)


_worker: ContinuousSelfMaintenance | None = None
_worker_lock = threading.Lock()


def start_continuous_self_maintenance() -> ContinuousSelfMaintenance | None:
    global _worker
    with _worker_lock:
        if _worker is None:
            worker = ContinuousSelfMaintenance()
            if not worker.configured:
                return None
            _worker = worker
            worker.start()
        return _worker
