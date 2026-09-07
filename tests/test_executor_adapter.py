from pathlib import Path

from coding.executor_adapter import SafeExecutorAdapter


class FakeTask:
    def __init__(self):
        self.status = "pending"
        self.error = None


class FakeExecutor:
    def __init__(self, action=None):
        self.action = action

    def execute_task(
        self,
        task,
        messages,
        tool_definitions,
        max_iterations=10,
    ):
        task.status = "completed"

        if self.action:
            self.action()

        yield {
            "type": "done",
            "content": "CODING_OK",
            "final": True,
        }


def collect(generator):
    events = []

    while True:
        try:
            events.append(next(generator))
        except StopIteration as stop:
            return events, stop.value


def test_safe_executor_success(tmp_path):
    target = tmp_path / "feature.py"

    executor = FakeExecutor(
        lambda: target.write_text(
            "print('hello')\n",
            encoding="utf-8",
        )
    )

    adapter = SafeExecutorAdapter(
        executor,
        tmp_path,
        ["feature.py"],
    )


    events, result = collect(
        adapter.execute(
            FakeTask(),
            [],
            [],
        )
    )

    assert result.completed is True
    assert result.rolled_back is False
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "print('hello')\n"

    statuses = [
        event.get("status")
        for event in events
        if event.get("type") == "coding_transaction"
    ]

    assert statuses == [
        "started",
        "surface_verified",
        "completed",
    ]


def test_failed_executor_rolls_back_existing_file(tmp_path):
    target = tmp_path / "feature.py"
    target.write_text(
        "ORIGINAL\n",
        encoding="utf-8",
    )

    class FailingExecutor:
        def execute_task(
            self,
            task,
            messages,
            tool_definitions,
            max_iterations=10,
        ):
            target.write_text(
                "BROKEN\n",
                encoding="utf-8",
            )

            task.status = "failed"
            task.error = "simulated failure"

            yield {
                "type": "done",
                "content": "failed",
                "final": True,
            }

    adapter = SafeExecutorAdapter(
        FailingExecutor(),
        tmp_path,
        ["feature.py"],
    )


    events, result = collect(
        adapter.execute(
            FakeTask(),
            [],
            [],
        )
    )

    assert result.completed is False
    assert result.rolled_back is True
    assert target.read_text(encoding="utf-8") == "ORIGINAL\n"

    assert any(
        event.get("type") == "coding_transaction"
        and event.get("status") == "rolled_back"
        for event in events
    )


def test_failed_tests_roll_back(tmp_path):
    target = tmp_path / "feature.py"
    target.write_text(
        "ORIGINAL\n",
        encoding="utf-8",
    )

    executor = FakeExecutor(
        lambda: target.write_text(
            "NEW\n",
            encoding="utf-8",
        )
    )

    adapter = SafeExecutorAdapter(
        executor,
        tmp_path,
        ["feature.py"],
    )


    events, result = collect(
        adapter.execute(
            FakeTask(),
            [],
            [],
            test_check=lambda: False,
        )
    )

    assert result.completed is False
    assert result.rolled_back is True
    assert target.read_text(encoding="utf-8") == "ORIGINAL\n"


def test_unexpected_change_is_detected(tmp_path):
    expected = tmp_path / "feature.py"
    unexpected = tmp_path / "unexpected.py"

    class ExecutorWithUnexpectedChange:
        def execute_task(
            self,
            task,
            messages,
            tool_definitions,
            max_iterations=10,
        ):
            expected.write_text(
                "EXPECTED\n",
                encoding="utf-8",
            )

            unexpected.write_text(
                "UNEXPECTED\n",
                encoding="utf-8",
            )

            task.status = "completed"

            yield {
                "type": "done",
                "content": "done",
                "final": True,
            }

    adapter = SafeExecutorAdapter(
        ExecutorWithUnexpectedChange(),
        tmp_path,
        ["feature.py"],
    )


    events, result = collect(
        adapter.execute(
            FakeTask(),
            [],
            [],
        )
    )

    assert result.completed is False
    assert result.rolled_back is True
    assert "unexpected.py" in result.unexpected_changes

    assert not expected.exists()
    assert unexpected.exists()


def test_protected_path_is_rejected(tmp_path):
    try:
        SafeExecutorAdapter(
            FakeExecutor(),
            tmp_path,
            ["Start-Friday.ps1"],
        )
    except Exception:
        return

    raise AssertionError(
        "Protected path should have been rejected."
    )