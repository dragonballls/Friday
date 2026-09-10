"""Runtime bridge between Friday's task events and the elastic worker pool.

This layer deliberately owns scheduling only. It does not execute tools or grant
permissions; execution remains the responsibility of Friday's existing Executor
and security/approval layers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.worker_manager import ElasticWorkerManager, WorkerSpec


@dataclass(frozen=True)
class WorkerAssignment:
    task_id: str
    worker_id: str
    role: str


class WorkerRuntime:
    """Translate task queue changes into worker lifecycle events."""

    def __init__(self, manager: ElasticWorkerManager | None = None) -> None:
        self.manager = manager or ElasticWorkerManager()
        self.assignments: dict[str, WorkerAssignment] = {}

    def reconcile(self, tasks: list[Any], spec: WorkerSpec) -> list[dict[str, Any]]:
        """Scale the pool and assign idle workers to queued tasks.

        The returned events are suitable for Friday's existing streaming event
        protocol. Actual execution is intentionally left to the Executor.
        """
        queued = [
            task for task in tasks
            if getattr(task, "status", "pending") in {"pending", "queued"}
        ]
        plan = self.manager.reconcile(len(queued), spec)
        events: list[dict[str, Any]] = [
            {
                "type": "worker_plan",
                "desired": plan.desired,
                "active": plan.active,
                "spawn": plan.spawn,
                "retire": plan.retire,
            }
        ]

        idle = list(self.manager.idle_workers)
        for task, worker in zip(queued, idle):
            task_id = str(getattr(task, "id", ""))
            if not task_id:
                continue
            self.manager.assign(worker.worker_id, task_id)
            assignment = WorkerAssignment(task_id, worker.worker_id, worker.spec.role)
            self.assignments[task_id] = assignment
            events.append(
                {
                    "type": "worker_assigned",
                    "task_id": task_id,
                    "worker_id": worker.worker_id,
                    "role": worker.spec.role,
                    "capabilities": sorted(worker.spec.capabilities),
                }
            )
        return events

    def complete(self, task_id: str) -> dict[str, Any] | None:
        assignment = self.assignments.pop(task_id, None)
        if assignment is None:
            return None
        self.manager.complete(assignment.worker_id)
        return {
            "type": "worker_completed",
            "task_id": assignment.task_id,
            "worker_id": assignment.worker_id,
        }

    def fail(self, task_id: str) -> dict[str, Any] | None:
        assignment = self.assignments.pop(task_id, None)
        if assignment is None:
            return None
        worker = self.manager.fail(assignment.worker_id)
        return {
            "type": "worker_failed",
            "task_id": assignment.task_id,
            "worker_id": worker.worker_id,
            "failures": worker.failures,
        }
