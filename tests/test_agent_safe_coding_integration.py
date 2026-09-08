from pathlib import Path

from agent.core import Agent


class FakeTask:
    def __init__(self, path: str):
        self.id = "coding_test"
        self.description = "write code"
        self.tool = "write_file"
        self.args = {
            "path": path,
            "content": "FRIDAY_STAGE_3E_OK\n",
        }
        self.dependencies = []
        self.status = "pending"
        self.result = None
        self.error = None
        self.retries = 0
        self.max_retries = 0

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


def test_agent_uses_safe_adapter_for_explicit_coding_task(tmp_path, monkeypatch):
    target = tmp_path / "feature.py"

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
            # This is reached while the real coding controller is still
            # executing. The session must not claim completion early.
            assert agent._coding_session.current_stage != "complete"
            assert agent._coding_session.status != "completed"

            Path(task.args["path"]).write_text(
                task.args["content"],
                encoding="utf-8",
            )
            task.status = "completed"

            yield {
                "type": "done",
                "content": "CODING_OK",
                "final": True,
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
    assert target.read_text(encoding="utf-8") == "FRIDAY_STAGE_3E_OK\n"

    statuses = [
        event.get("status")
        for event in events
        if event.get("type") == "coding_transaction"
    ]

    assert "started" in statuses
    assert "surface_verified" in statuses
    assert "completed" in statuses

    completed_event = next(
        event
        for event in events
        if event.get("type") == "coding_transaction"
        and event.get("status") == "completed"
    )

    assert completed_event.get("transaction_id")

    # The session is persisted only after the controller has passed all
    # coding gates and the Agent has finalized the successful transaction.
    session_state = agent._coding_session_state
    assert session_state["status"] == "completed"
    assert session_state["current_stage"] == "complete"
    assert session_state["checkpoint"] == "coding-complete"
    assert session_state["confidence"] == "high"
    assert session_state["attempt"] >= 1
    assert session_state["changes"]
    assert session_state["tests"]


def test_agent_rejects_coding_without_explicit_path(tmp_path):
    agent = object.__new__(Agent)
    agent._output_dir = str(tmp_path)
    agent._tool_defs = []
    agent.messages = []

    task = FakeTask(str(tmp_path / "feature.py"))
    task.args = {
        "content": "FRIDAY_STAGE_3E_OK\n"
    }

    events = list(
        agent._execute_coding_task(
            task,
            10,
        )
    )

    assert task.status == "failed"
    assert any(
        event.get("status") == "rejected"
        for event in events
    )

