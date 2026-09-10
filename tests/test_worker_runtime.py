from types import SimpleNamespace

from core.worker_manager import Capacity, ElasticWorkerManager, WorkerSpec
from core.worker_runtime import WorkerRuntime


def test_runtime_assigns_queued_tasks_and_emits_real_worker_events() -> None:
    manager = ElasticWorkerManager(
        min_workers=1,
        normal_workers=2,
        burst_workers=4,
        max_workers=8,
        capacity_provider=lambda: Capacity(cloud_available=4, local_available=1),
    )
    runtime = WorkerRuntime(manager)
    tasks = [SimpleNamespace(id="task-1", status="queued"), SimpleNamespace(id="task-2", status="pending")]

    events = runtime.reconcile(
        tasks,
        WorkerSpec("coder", frozenset({"filesystem.read", "tests"})),
    )

    assert events[0]["type"] == "worker_plan"
    assignments = [event for event in events if event["type"] == "worker_assigned"]
    assert {event["task_id"] for event in assignments} == {"task-1", "task-2"}
    assert all(event["role"] == "coder" for event in assignments)
    assert all(event["capabilities"] == ["filesystem.read", "tests"] for event in assignments)


def test_runtime_completion_releases_worker_for_reuse() -> None:
    runtime = WorkerRuntime(
        ElasticWorkerManager(min_workers=1, normal_workers=1, burst_workers=2, max_workers=4)
    )
    task = SimpleNamespace(id="repair-1", status="queued")
    runtime.reconcile([task], WorkerSpec("coder"))

    completed = runtime.complete("repair-1")

    assert completed is not None
    assert completed["type"] == "worker_completed"
    assert len(runtime.manager.idle_workers) == 1


def test_runtime_failure_releases_task_assignment_without_deleting_task_id_from_event() -> None:
    runtime = WorkerRuntime(
        ElasticWorkerManager(min_workers=1, normal_workers=1, burst_workers=2, max_workers=4)
    )
    task = SimpleNamespace(id="repair-2", status="queued")
    runtime.reconcile([task], WorkerSpec("coder"))

    failed = runtime.fail("repair-2")

    assert failed is not None
    assert failed["type"] == "worker_failed"
    assert failed["task_id"] == "repair-2"
    assert failed["failures"] == 1
    assert runtime.assignments == {}
