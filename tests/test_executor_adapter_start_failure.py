from coding.executor_adapter import SafeExecutorAdapter


class FakeTask:
    def __init__(self):
        self.status = "pending"
        self.error = None


class FakeExecutor:
    def execute_task(self, task, messages, tool_definitions, max_iterations=10):
        task.status = "completed"
        yield {"type": "done", "final": True}


def test_start_failure_does_not_mask_original_error(tmp_path):
    adapter = SafeExecutorAdapter(
        FakeExecutor(),
        tmp_path,
        ["feature.py"],
    )

    original_error = RuntimeError("transaction start failed")

    def fail_start():
        raise original_error

    adapter.run.start = fail_start
    task = FakeTask()

    generator = adapter.execute(task, [], [])
    events = []
    while True:
        try:
            events.append(next(generator))
        except StopIteration as stop:
            result = stop.value
            break

    assert task.status == "failed"
    assert task.error == str(original_error)
    assert result.completed is False
    assert result.rolled_back is False
    assert any(
        event.get("type") == "coding_transaction"
        and event.get("status") == "failed"
        and event.get("error") == str(original_error)
        for event in events
    )
