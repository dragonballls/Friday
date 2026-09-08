from pathlib import Path

from coding.executor_adapter import SafeExecutorAdapter


class FakeTask:
    status = "pending"
    error = None


class FakeExecutor:
    def execute_task(self, task, messages, tool_definitions, max_iterations=10):
        target = Path(messages[0]["target"])
        target.write_text("changed\n", encoding="utf-8")
        task.status = "completed"
        yield {"type": "done", "content": "done"}


def test_real_git_workspace_cannot_complete_without_repository_verification(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    target = tmp_path / "feature.py"
    target.write_text("original\n", encoding="utf-8")

    monkeypatch.setattr(
        SafeExecutorAdapter,
        "_run_repository_verification",
        lambda self: {
            "success": False,
            "all_gates_passed": False,
            "message": "verification failed",
            "gates": [{"name": "backend_tests", "passed": False}],
        },
    )

    adapter = SafeExecutorAdapter(FakeExecutor(), tmp_path, ["feature.py"])
    task = FakeTask()
    events = list(
        adapter.execute(
            task,
            [{"target": str(target)}],
            [],
        )
    )

    assert target.read_text(encoding="utf-8") == "original\n"
    assert any(
        event.get("type") == "coding_transaction"
        and event.get("status") == "rolled_back"
        for event in events
    )
    assert any(
        event.get("type") == "verification"
        and event.get("success") is False
        for event in events
    )
