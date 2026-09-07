from pathlib import Path

from agent.core import Agent


class FakeTask:
    def __init__(self, path: str):
        self.id = "coding_retry_test"
        self.description = "write code"
        self.tool = "write_file"
        self.args = {
            "path": path,
            "content": "FRIDAY_STAGE_3G_OK\n",
        }
        self.dependencies = []
        self.status = "failed"
        self.result = None
        self.error = "intentional coding failure"
        self.retries = 1
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


def test_coding_retry_reenters_safe_adapter(tmp_path):
    target = tmp_path / "retry_feature.py"

    agent = object.__new__(Agent)
    agent._output_dir = str(tmp_path)
    agent._tool_defs = []
    agent.messages = []

    class FakeExecutor:
        output_dir = None

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

    agent._executor = FakeExecutor()

    task = FakeTask(str(target))

    events = list(
        agent._execute_coding_task(
            task,
            10,
        )
    )

    assert target.exists()
    assert target.read_text(encoding="utf-8") == "FRIDAY_STAGE_3G_OK\n"

    transaction_events = [
        event
        for event in events
        if event.get("type") == "coding_transaction"
    ]

    statuses = [
        event.get("status")
        for event in transaction_events
    ]

    assert "started" in statuses
    assert "surface_verified" in statuses
    assert "completed" in statuses

def test_adaptive_retry_changes_strategy_between_failed_attempts():
    from coding.attempt_history import CodingAttemptHistory

    history = CodingAttemptHistory()

    first = history.choose_repair_strategy(
        "TEST_FAILURE",
        "inspect the failing test first",
    )

    history.record(
        1,
        success=False,
        failure_class="TEST_FAILURE",
        error="first attempt failed",
        strategy=first,
        recommended_action="inspect the failing test first",
    )

    second = history.choose_repair_strategy(
        "TEST_FAILURE",
        "inspect the failing test first",
    )

    history.record(
        2,
        success=True,
        strategy=second,
        recommended_action="inspect the failing test first",
    )

    assert first != second
    assert history.failures[0].strategy == first
    assert history.last.strategy == second
    assert history.has_failed_strategy(first)
    assert not history.has_failed_strategy(second)
    assert history.last.success is True