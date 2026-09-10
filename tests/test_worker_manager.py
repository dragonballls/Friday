from core.worker_manager import Capacity, ElasticWorkerManager, WorkerSpec, WorkerState


def test_queue_pressure_expands_worker_pool() -> None:
    manager = ElasticWorkerManager(min_workers=1, normal_workers=4, burst_workers=8, max_workers=12)

    plan = manager.reconcile(10, WorkerSpec("coder", frozenset({"filesystem.read", "tests"})))

    assert plan.desired == 5
    assert plan.active == 5
    assert plan.spawn == 0
    assert all(worker.spec.role == "coder" for worker in manager.active_workers)


def test_worker_failure_does_not_delete_task_identity_from_external_ledger() -> None:
    manager = ElasticWorkerManager(min_workers=1, normal_workers=2, burst_workers=4, max_workers=8)
    worker = manager.spawn(WorkerSpec("coder"))[0]
    manager.assign(worker.worker_id, "repair-421")

    failed = manager.fail(worker.worker_id)

    assert failed.state is WorkerState.FAILED
    assert failed.task_id == "repair-421"
    assert manager.active_workers == []


def test_idle_workers_can_be_retired_without_retiring_running_workers() -> None:
    manager = ElasticWorkerManager(min_workers=1, normal_workers=2, burst_workers=4, max_workers=8)
    workers = manager.spawn(WorkerSpec("coder"), 3)
    manager.assign(workers[0].worker_id, "task-1")

    retired = manager.retire_idle(2)

    assert len(retired) == 2
    assert all(worker.state is WorkerState.RETIRING for worker in retired)
    assert manager.workers[workers[0].worker_id].state is WorkerState.RUNNING
    assert len(manager.active_workers) == 1


def test_cloud_capacity_limits_workers_without_using_local_capacity() -> None:
    manager = ElasticWorkerManager(
        min_workers=1,
        normal_workers=4,
        burst_workers=8,
        max_workers=16,
        capacity_provider=lambda: Capacity(cloud_available=3, local_available=0),
    )

    plan = manager.reconcile(20, WorkerSpec("research"))

    assert plan.desired == 3
    assert plan.active == 3


def test_zero_cloud_capacity_means_no_cloud_workers() -> None:
    manager = ElasticWorkerManager(
        min_workers=1,
        normal_workers=4,
        burst_workers=8,
        max_workers=16,
        capacity_provider=lambda: Capacity(cloud_available=0, local_available=8),
    )

    plan = manager.plan(20)

    assert plan.desired == 0
    assert plan.spawn == 0


def test_worker_capabilities_do_not_change_when_pool_scales() -> None:
    spec = WorkerSpec("github", frozenset({"github.read", "github.branch"}))
    manager = ElasticWorkerManager(min_workers=1, normal_workers=4, burst_workers=8, max_workers=16)

    manager.reconcile(12, spec)

    assert len(manager.active_workers) == 6
    assert all(worker.spec.capabilities == spec.capabilities for worker in manager.active_workers)
