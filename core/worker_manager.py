"""Elastic worker scheduling primitives for Friday.

The manager deliberately separates worker scaling from tool authority. A larger
worker pool increases parallel task capacity but never grants additional
capabilities to a worker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable
from uuid import uuid4


class WorkerState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    RETIRING = "retiring"
    FAILED = "failed"


@dataclass(frozen=True)
class WorkerSpec:
    """Role and capabilities assigned to a worker."""

    role: str
    capabilities: frozenset[str] = frozenset()


@dataclass
class Worker:
    """Runtime state for one replaceable worker."""

    spec: WorkerSpec
    worker_id: str = field(default_factory=lambda: f"worker-{uuid4().hex[:10]}")
    state: WorkerState = WorkerState.IDLE
    task_id: str | None = None
    failures: int = 0


@dataclass(frozen=True)
class Capacity:
    """Current capacity available to the scheduler."""

    cloud_available: int
    local_available: int


@dataclass(frozen=True)
class WorkerPlan:
    """Desired worker counts produced by a reconciliation pass."""

    desired: int
    active: int
    spawn: int
    retire: int


class ElasticWorkerManager:
    """Scale a replaceable pool from queue pressure and available capacity."""

    def __init__(
        self,
        *,
        min_workers: int = 1,
        normal_workers: int = 4,
        burst_workers: int = 16,
        max_workers: int = 32,
        tasks_per_worker: int = 2,
        capacity_provider: Callable[[], Capacity] | None = None,
    ) -> None:
        if not 0 <= min_workers <= normal_workers <= burst_workers <= max_workers:
            raise ValueError("worker limits must be ordered and non-negative")
        if tasks_per_worker < 1:
            raise ValueError("tasks_per_worker must be at least 1")

        self.min_workers = min_workers
        self.normal_workers = normal_workers
        self.burst_workers = burst_workers
        self.max_workers = max_workers
        self.tasks_per_worker = tasks_per_worker
        self._capacity_provider = capacity_provider or (
            lambda: Capacity(cloud_available=max_workers, local_available=1)
        )
        self.workers: dict[str, Worker] = {}

    @property
    def active_workers(self) -> list[Worker]:
        return [
            worker
            for worker in self.workers.values()
            if worker.state in {WorkerState.IDLE, WorkerState.RUNNING}
        ]

    @property
    def idle_workers(self) -> list[Worker]:
        return [worker for worker in self.active_workers if worker.state == WorkerState.IDLE]

    def desired_count(self, queued_tasks: int) -> int:
        """Return a bounded desired cloud-worker count for the current queue."""
        if queued_tasks < 0:
            raise ValueError("queued_tasks cannot be negative")
        if queued_tasks == 0:
            return self.min_workers

        demand = (queued_tasks + self.tasks_per_worker - 1) // self.tasks_per_worker
        if queued_tasks <= self.burst_workers * self.tasks_per_worker:
            target = max(self.normal_workers, demand)
        else:
            target = max(self.burst_workers, demand)
        return min(self.max_workers, target)

    def plan(self, queued_tasks: int) -> WorkerPlan:
        """Calculate scaling without mutating the pool."""
        capacity = self._capacity_provider()
        active = len(self.active_workers)
        desired = min(self.desired_count(queued_tasks), max(0, capacity.cloud_available))
        if capacity.cloud_available > 0:
            desired = max(self.min_workers, desired)
        return WorkerPlan(
            desired=desired,
            active=active,
            spawn=max(0, desired - active),
            retire=max(0, active - desired),
        )

    def spawn(self, spec: WorkerSpec, count: int = 1) -> list[Worker]:
        """Create idle workers without assigning them authority beyond ``spec``."""
        if count < 1:
            return []
        available = max(0, self.max_workers - len(self.active_workers))
        count = min(count, available)
        created = [Worker(spec=spec) for _ in range(count)]
        self.workers.update({worker.worker_id: worker for worker in created})
        return created

    def assign(self, worker_id: str, task_id: str) -> Worker:
        """Assign a task to an idle worker."""
        worker = self.workers[worker_id]
        if worker.state != WorkerState.IDLE:
            raise ValueError("worker is not idle")
        worker.task_id = task_id
        worker.state = WorkerState.RUNNING
        return worker

    def complete(self, worker_id: str) -> Worker:
        """Return a completed worker to the idle pool."""
        worker = self.workers[worker_id]
        worker.task_id = None
        worker.state = WorkerState.IDLE
        return worker

    def fail(self, worker_id: str) -> Worker:
        """Mark a worker failed; its task remains external to this worker object."""
        worker = self.workers[worker_id]
        worker.failures += 1
        worker.state = WorkerState.FAILED
        return worker

    def retire_idle(self, count: int) -> list[Worker]:
        """Retire up to ``count`` idle workers, never active workers."""
        retired: list[Worker] = []
        for worker in self.idle_workers[: max(0, count)]:
            worker.state = WorkerState.RETIRING
            retired.append(worker)
        return retired

    def reconcile(self, queued_tasks: int, spec: WorkerSpec) -> WorkerPlan:
        """Scale toward the current plan and return the resulting plan."""
        plan = self.plan(queued_tasks)
        if plan.spawn:
            self.spawn(spec, plan.spawn)
        elif plan.retire:
            self.retire_idle(plan.retire)
        return self.plan(queued_tasks)
