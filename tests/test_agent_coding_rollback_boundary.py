from pathlib import Path

from coding.executor_adapter import SafeExecutorAdapter


class FakeTask:
    def __init__(self, path: str, content: str = "NEW_CONTENT\n"):
        self.id = "rollback_boundary"
        self.description = "write code"
        self.tool = "write_file"
        self.args = {
            "path": path,
            "content": content,
        }
        self.dependencies = []
        self.status = "pending"
        self.result = None
        self.error = None
        self.retries = 0
        self.max_retries = 3

    def to_dict(self):
        return {
            "id": self.id,
            "description": self.description,
            "tool": self.tool,
            "args": self.args,
            "dependencies": self.dependencies,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "retries": self.retries,
            "max_retries": self.max_retries,
        }


class WritingExecutor:
    output_dir = None

    def __init__(self, extra_path=None):
        self.extra_path = extra_path

    def execute_task(
        self,
        task,
        messages,
        tool_definitions,
        max_iterations=10,
    ):
        Path(task.args["path"]).write_text(
            task.args["content"],
            encoding="utf-8",
        )

        if self.extra_path is not None:
            Path(self.extra_path).write_text(
                "UNAUTHORIZED_CHANGE\n",
                encoding="utf-8",
            )

        task.status = "completed"

        yield {
            "type": "tool_result",
            "tools": [
                {
                    "tool": "write_file",
                    "success": True,
                }
            ],
        }


def make_adapter(tmp_path, target, extra_path=None):
    return SafeExecutorAdapter(
        executor=WritingExecutor(extra_path=extra_path),
        workspace=tmp_path,
        expected_paths=[target],
    )


def test_failed_final_verification_rolls_back_authorized_file(tmp_path):
    target = tmp_path / "feature.py"
    target.write_text(
        "ORIGINAL_CONTENT\n",
        encoding="utf-8",
    )

    adapter = make_adapter(tmp_path, target)
    task = FakeTask(
        str(target),
        "MODIFIED_CONTENT\n",
    )

    events = list(
        adapter.execute(
            task,
            [],
            [],
            final_verification_check=lambda: False,
        )
    )

    assert target.read_text(encoding="utf-8") == "ORIGINAL_CONTENT\n"

    rollback_events = [
        event
        for event in events
        if event.get("type") == "coding_transaction"
    ]

    assert any(
        event.get("status") == "rolled_back"
        for event in rollback_events
    )


def test_unauthorized_change_is_detected(tmp_path):
    target = tmp_path / "feature.py"
    unauthorized = tmp_path / "secret.py"

    target.write_text(
        "ORIGINAL_CONTENT\n",
        encoding="utf-8",
    )

    adapter = make_adapter(
        tmp_path,
        target,
        extra_path=unauthorized,
    )

    task = FakeTask(
        str(target),
        "AUTHORIZED_CHANGE\n",
    )

    events = list(
        adapter.execute(
            task,
            [],
            [],
        )
    )

    assert target.read_text(encoding="utf-8") == "ORIGINAL_CONTENT\n"

    # The safety boundary detects unauthorized mutations but does
    # not silently delete files it was never authorized to touch.
    # The authorized file must still be restored.
    assert unauthorized.exists()
    assert unauthorized.read_text(encoding="utf-8") == "UNAUTHORIZED_CHANGE\n"

    rollback_events = [
        event
        for event in events
        if event.get("type") == "coding_transaction"
    ]

    assert any(
        event.get("status") == "rolled_back"
        for event in rollback_events
    )

    assert any(
        "secret.py" in str(event.get("unexpected_changes", []))
        for event in rollback_events
    )


def test_test_gate_failure_rolls_back_authorized_file(tmp_path):
    target = tmp_path / "feature.py"

    target.write_text(
        "ORIGINAL_CONTENT\n",
        encoding="utf-8",
    )

    adapter = make_adapter(tmp_path, target)
    task = FakeTask(
        str(target),
        "TEST_GATE_CHANGE\n",
    )

    events = list(
        adapter.execute(
            task,
            [],
            [],
            implementation_check=lambda: True,
            test_check=lambda: False,
            review_check=lambda: True,
            final_verification_check=lambda: True,
        )
    )

    assert target.read_text(encoding="utf-8") == "ORIGINAL_CONTENT\n"

    rollback_events = [
        event
        for event in events
        if event.get("type") == "coding_transaction"
    ]

    assert any(
        event.get("status") == "rolled_back"
        for event in rollback_events
    )