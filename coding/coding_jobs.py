"""Persistent background coding-job orchestration for Friday.

This module owns job lifecycle and worker coordination.

It deliberately does NOT perform filesystem mutation itself.
Actual coding must be supplied through an injected runner, which keeps
the existing SafeCodingRun / SafeExecutorAdapter boundary in control of
source modifications.
"""

from __future__ import annotations

import json
import os
import threading
import time
import traceback
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_state_dir() -> Path:
    """Return persistent job storage outside the Friday source tree."""
    root = os.environ.get("LOCALAPPDATA")
    if root:
        return Path(root) / "Friday" / "coding-jobs"

    return Path.home() / ".friday" / "coding-jobs"


@dataclass
class CodingJob:
    job_id: str
    goal: str
    workspace: str = ""
    status: str = "queued"

    created_at: str = field(default_factory=_utc_now)
    started_at: str | None = None
    finished_at: str | None = None

    time_budget_seconds: float | None = None
    deadline: float | None = None

    stage: str = "queued"
    attempt: int = 0

    requirements: list[str] = field(default_factory=list)
    expected_paths: list[str] = field(default_factory=list)

    events: list[dict[str, Any]] = field(default_factory=list)
    failures: list[dict[str, Any]] = field(default_factory=list)
    lessons: list[str] = field(default_factory=list)

    result: dict[str, Any] | None = None
    error: str | None = None

    pause_requested: bool = False
    cancel_requested: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation of this job."""
        data = asdict(self)

        def _json_safe(value: Any) -> Any:
            if isinstance(value, dict):
                return {
                    str(key): _json_safe(item)
                    for key, item in value.items()
                }

            if isinstance(value, (list, tuple, set, frozenset)):
                return [_json_safe(item) for item in value]

            if isinstance(value, Path):
                return str(value)

            return value

        return _json_safe(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CodingJob":
        allowed = {
            "job_id",
            "goal",
            "workspace",
            "status",
            "created_at",
            "started_at",
            "finished_at",
            "time_budget_seconds",
            "deadline",
            "stage",
            "attempt",
            "requirements",
            "expected_paths",
            "events",
            "failures",
            "lessons",
            "result",
            "error",
            "pause_requested",
            "cancel_requested",
        }

        values = {key: value for key, value in data.items() if key in allowed}
        return cls(**values)


class CodingJobError(RuntimeError):
    """Base error for background coding jobs."""


class CodingJobNotFound(CodingJobError):
    """Raised when a requested job does not exist."""


class CodingJobManager:
    """Thread-safe persistent manager for long-running coding jobs.

    The manager owns lifecycle, persistence, control signals, and events.
    It does not edit source files.

    A runner is injected at construction time:

        runner(job, manager)

    The runner may perform the actual coding work, but it must use Friday's
    existing safe coding boundary for any source mutation.
    """

    TERMINAL_STATES = frozenset(
        {
            "completed",
            "failed",
            "cancelled",
            "expired",
        }
    )

    ACTIVE_STATES = frozenset(
        {
            "queued",
            "running",
            "paused",
        }
    )

    def __init__(
        self,
        runner: Callable[[CodingJob, "CodingJobManager"], Any] | None = None,
        state_dir: str | Path | None = None,
    ) -> None:
        self.runner = runner

        self.state_dir = Path(state_dir or _default_state_dir()).expanduser().resolve()
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)

        self._jobs: dict[str, CodingJob] = {}
        self._worker: threading.Thread | None = None
        self._shutdown = False

        self._load_jobs()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _job_path(self, job_id: str) -> Path:
        return self.state_dir / f"{job_id}.json"

    def _save_job_locked(self, job: CodingJob) -> None:
        path = self._job_path(job.job_id)
        temporary = path.with_suffix(".json.tmp")

        payload = json.dumps(
            job.to_dict(),
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )

        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(path)

    def _load_jobs(self) -> None:
        for path in sorted(self.state_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                job = CodingJob.from_dict(data)
                self._jobs[job.job_id] = job
            except Exception:
                # A corrupt historical job must never prevent Friday from
                # starting. Preserve it for diagnosis rather than deleting it.
                continue

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def _emit_locked(
        self,
        job: CodingJob,
        event_type: str,
        message: str = "",
        **data: Any,
    ) -> dict[str, Any]:
        event = {
            "timestamp": _utc_now(),
            "job_id": job.job_id,
            "type": event_type,
            "message": message,
            **data,
        }

        job.events.append(event)

        # Keep persistent job records bounded.
        if len(job.events) > 500:
            del job.events[:-500]

        self._save_job_locked(job)
        return event

    def emit(
        self,
        job_id: str,
        event_type: str,
        message: str = "",
        **data: Any,
    ) -> dict[str, Any]:
        with self._lock:
            job = self._get_locked(job_id)
            return self._emit_locked(job, event_type, message, **data)

    # ------------------------------------------------------------------
    # Job creation / lookup
    # ------------------------------------------------------------------

    def create_job(
        self,
        goal: str,
        *,
        workspace: str | Path | None = None,
        time_budget_seconds: float | None = None,
        expected_paths: list[str] | tuple[str, ...] | None = None,
        requirements: list[str] | tuple[str, ...] | None = None,
    ) -> CodingJob:
        goal = str(goal or "").strip()
        workspace_value = Path(workspace or Path.cwd()).expanduser().resolve()

        if not goal:
            raise CodingJobError("Coding job requires a non-empty goal.")

        if not workspace_value.exists() or not workspace_value.is_dir:
            raise CodingJobError(
                f"Coding job workspace does not exist: {workspace_value}"
            )

        if not workspace_value.exists() or not workspace_value.is_dir():
            raise CodingJobError(
                f"Coding job workspace does not exist: {workspace_value}"
            )

        if time_budget_seconds is not None:
            time_budget_seconds = float(time_budget_seconds)

            if time_budget_seconds <= 0:
                raise CodingJobError(
                    "Coding job time budget must be greater than zero."
                )

        job_id = uuid.uuid4().hex[:12]

        now = time.time()
        deadline = (
            now + time_budget_seconds
            if time_budget_seconds is not None
            else None
        )

        job = CodingJob(
            job_id=job_id,
            goal=goal,
            workspace=str(workspace_value),
            time_budget_seconds=time_budget_seconds,
            deadline=deadline,
            expected_paths=list(expected_paths or ()),
            requirements=list(requirements or ()),
        )

        with self._condition:
            self._jobs[job_id] = job
            self._emit_locked(
                job,
                "created",
                "Background coding job created.",
            )
            self._condition.notify_all()

        return self.get_job(job_id)

    def _get_locked(self, job_id: str) -> CodingJob:
        job = self._jobs.get(str(job_id))
        if job is None:
            raise CodingJobNotFound(f"Coding job not found: {job_id}")
        return job

    def get_job(self, job_id: str) -> CodingJob:
        with self._lock:
            job = self._get_locked(job_id)

            # Return a detached object so callers cannot mutate manager state
            # without acquiring the manager lock.
            return CodingJob.from_dict(job.to_dict())

    def list_jobs(self) -> list[CodingJob]:
        with self._lock:
            return [
                CodingJob.from_dict(job.to_dict())
                for job in sorted(
                    self._jobs.values(),
                    key=lambda item: item.created_at,
                    reverse=True,
                )
            ]

    # ------------------------------------------------------------------
    # Worker lifecycle
    # ------------------------------------------------------------------

    def start(self, job_id: str) -> CodingJob:
        with self._condition:
            job = self._get_locked(job_id)

            if job.status in self.TERMINAL_STATES:
                raise CodingJobError(
                    f"Cannot start terminal coding job: {job.status}"
                )

            if self._worker is not None and self._worker.is_alive():
                active = [
                    item
                    for item in self._jobs.values()
                    if item.status == "running"
                ]

                if active and active[0].job_id != job.job_id:
                    raise CodingJobError(
                        "Another coding job is already running."
                    )

            job.pause_requested = False
            job.cancel_requested = False

            if job.status == "paused":
                job.status = "queued"
                job.stage = "queued"

            self._emit_locked(
                job,
                "queued",
                "Coding job queued for background execution.",
            )

            self._ensure_worker_locked()
            self._condition.notify_all()

            return CodingJob.from_dict(job.to_dict())

    def _ensure_worker_locked(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            return

        self._worker = threading.Thread(
            target=self._worker_main,
            name="Friday-CodingWorker",
            daemon=True,
        )
        self._worker.start()

    def _next_queued_job_locked(self) -> CodingJob | None:
        queued = [
            job
            for job in self._jobs.values()
            if job.status == "queued"
            and not job.cancel_requested
        ]

        if not queued:
            return None

        queued.sort(key=lambda item: item.created_at)
        return queued[0]

    def _worker_main(self) -> None:
        while True:
            with self._condition:
                while not self._shutdown:
                    job = self._next_queued_job_locked()

                    if job is not None:
                        break

                    self._condition.wait(timeout=1.0)

                if self._shutdown:
                    return

                job.status = "running"
                job.stage = "starting"
                job.started_at = job.started_at or _utc_now()

                self._emit_locked(
                    job,
                    "started",
                    "Background coding worker started.",
                )

            self._run_job(job.job_id)

    def _run_job(self, job_id: str) -> None:
        try:
            with self._lock:
                job = self._get_locked(job_id)

                if self._deadline_expired_locked(job):
                    self._expire_locked(job)
                    return

                if self.runner is None:
                    raise CodingJobError(
                        "No coding runner is attached to CodingJobManager."
                    )

            result = self.runner(job, self)

            with self._condition:
                job = self._get_locked(job_id)

                if job.status in self.TERMINAL_STATES:
                    return

                if job.cancel_requested:
                    self._cancel_locked(
                        job,
                        "Coding job cancelled by request.",
                    )
                    return

                if self._deadline_expired_locked(job):
                    self._expire_locked(job)
                    return

                success = False

                if isinstance(result, bool):
                    success = result
                elif isinstance(result, dict):
                    success = bool(
                        result.get("completed")
                        or result.get("success")
                        or result.get("verified")
                    )
                    job.result = result
                elif result is not None:
                    job.result = {"value": repr(result)}
                    success = bool(result)

                if success:
                    job.status = "completed"
                    job.stage = "completed"
                    job.finished_at = _utc_now()
                    self._emit_locked(
                        job,
                        "completed",
                        "Background coding job completed successfully.",
                    )
                else:
                    job.status = "failed"
                    job.stage = "failed"
                    job.finished_at = _utc_now()
                    job.error = job.error or "Coding runner reported failure."

                    self._emit_locked(
                        job,
                        "failed",
                        job.error,
                    )

        except Exception as exc:
            with self._condition:
                job = self._get_locked(job_id)

                job.status = "failed"
                job.stage = "failed"
                job.finished_at = _utc_now()
                job.error = str(exc)

                failure = {
                    "timestamp": _utc_now(),
                    "type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                }

                job.failures.append(failure)

                self._emit_locked(
                    job,
                    "failed",
                    f"Background coding worker failed: {exc}",
                )

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------

    def pause(self, job_id: str) -> CodingJob:
        with self._condition:
            job = self._get_locked(job_id)

            if job.status == "queued":
                job.status = "paused"
                job.stage = "paused"
            elif job.status == "running":
                job.pause_requested = True
            else:
                raise CodingJobError(
                    f"Cannot pause coding job in state: {job.status}"
                )

            self._emit_locked(
                job,
                "pause_requested",
                "Pause requested. The worker will stop at the next safe boundary.",
            )
            self._condition.notify_all()

            return CodingJob.from_dict(job.to_dict())

    def resume(self, job_id: str) -> CodingJob:
        with self._condition:
            job = self._get_locked(job_id)

            if job.status not in {"paused", "queued"}:
                raise CodingJobError(
                    f"Cannot resume coding job in state: {job.status}"
                )

            job.pause_requested = False
            job.cancel_requested = False
            job.status = "queued"
            job.stage = "queued"

            self._emit_locked(
                job,
                "resumed",
                "Coding job resumed.",
            )

            self._ensure_worker_locked()
            self._condition.notify_all()

            return CodingJob.from_dict(job.to_dict())

    def cancel(self, job_id: str) -> CodingJob:
        with self._condition:
            job = self._get_locked(job_id)

            if job.status in self.TERMINAL_STATES:
                return CodingJob.from_dict(job.to_dict())

            job.cancel_requested = True

            if job.status == "queued":
                self._cancel_locked(
                    job,
                    "Coding job cancelled before execution.",
                )
            elif job.status == "paused":
                self._cancel_locked(
                    job,
                    "Coding job cancelled while paused.",
                )
            else:
                self._emit_locked(
                    job,
                    "cancel_requested",
                    "Cancellation requested. The worker will stop at the next safe boundary.",
                )

            self._condition.notify_all()

            return CodingJob.from_dict(job.to_dict())

    def add_requirement(self, job_id: str, requirement: str) -> CodingJob:
        requirement = str(requirement or "").strip()

        if not requirement:
            raise CodingJobError("Requirement cannot be empty.")

        with self._condition:
            job = self._get_locked(job_id)

            if job.status in self.TERMINAL_STATES:
                raise CodingJobError(
                    "Cannot add a requirement to a terminal coding job."
                )

            job.requirements.append(requirement)

            self._emit_locked(
                job,
                "requirement_added",
                "New requirement added to coding job.",
                requirement=requirement,
            )

            self._condition.notify_all()

            return CodingJob.from_dict(job.to_dict())

    # ------------------------------------------------------------------
    # Worker-safe coordination helpers
    # ------------------------------------------------------------------

    def checkpoint(
        self,
        job_id: str,
        *,
        stage: str | None = None,
        attempt: int | None = None,
        message: str = "",
        **data: Any,
    ) -> bool:
        """Record progress and return whether execution may continue."""

        with self._condition:
            job = self._get_locked(job_id)

            if stage:
                job.stage = stage

            if attempt is not None:
                job.attempt = int(attempt)

            if self._deadline_expired_locked(job):
                self._expire_locked(job)
                return False

            if job.cancel_requested:
                self._cancel_locked(
                    job,
                    "Cancellation reached a safe worker boundary.",
                )
                return False

            if job.pause_requested:
                job.status = "paused"
                job.stage = "paused"

                self._emit_locked(
                    job,
                    "paused",
                    "Coding worker paused at a safe boundary.",
                )

                return False

            if message or data:
                self._emit_locked(
                    job,
                    "progress",
                    message,
                    stage=job.stage,
                    attempt=job.attempt,
                    **data,
                )
            else:
                self._save_job_locked(job)

            return True

    def wait_if_paused(self, job_id: str) -> bool:
        """Block until resumed/cancelled/expired.

        Returns False when the worker must stop.
        """

        with self._condition:
            job = self._get_locked(job_id)

            while job.pause_requested and not self._shutdown:
                job.status = "paused"
                job.stage = "paused"
                self._save_job_locked(job)

                self._condition.wait(timeout=1.0)

                job = self._get_locked(job_id)

                if self._deadline_expired_locked(job):
                    self._expire_locked(job)
                    return False

                if job.cancel_requested:
                    self._cancel_locked(
                        job,
                        "Coding job cancelled while paused.",
                    )
                    return False

            if job.status == "paused":
                job.status = "running"
                job.stage = "resuming"

                self._emit_locked(
                    job,
                    "resuming",
                    "Coding worker resumed.",
                )

            return not job.cancel_requested and not self._deadline_expired_locked(job)

    def remaining_seconds(self, job_id: str) -> float | None:
        with self._lock:
            job = self._get_locked(job_id)

            if job.deadline is None:
                return None

            return max(0.0, job.deadline - time.time())

    def is_cancelled(self, job_id: str) -> bool:
        with self._lock:
            return self._get_locked(job_id).cancel_requested

    # ------------------------------------------------------------------
    # Terminal state helpers
    # ------------------------------------------------------------------

    def _deadline_expired_locked(self, job: CodingJob) -> bool:
        return (
            job.deadline is not None
            and time.time() >= job.deadline
        )

    def _expire_locked(self, job: CodingJob) -> None:
        job.status = "expired"
        job.stage = "expired"
        job.finished_at = _utc_now()
        job.error = "Coding job time budget expired."

        self._emit_locked(
            job,
            "expired",
            job.error,
        )

    def _cancel_locked(self, job: CodingJob, message: str) -> None:
        job.status = "cancelled"
        job.stage = "cancelled"
        job.finished_at = _utc_now()

        self._emit_locked(
            job,
            "cancelled",
            message,
        )

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def shutdown(self, wait: bool = False) -> None:
        with self._condition:
            self._shutdown = True
            self._condition.notify_all()

        worker = self._worker

        if wait and worker is not None:
            worker.join(timeout=10.0)


__all__ = [
    "CodingJob",
    "CodingJobError",
    "CodingJobManager",
    "CodingJobNotFound",
]