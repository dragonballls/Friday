from agent.core import _is_coding_task


class TaskStub:
    def __init__(self, tool, description, args=None):
        self.tool = tool
        self.description = description
        self.args = args or {}


def test_only_mutations_use_safe_coding_boundary(tmp_path):
    path = str(tmp_path / "feature.py")

    assert _is_coding_task(TaskStub("write_file", "write code", {"path": path}))
    assert _is_coding_task(TaskStub("none", "edit this file", {"path": path}))

    for tool in ("run_tests", "review_code_change", "verify_coding_change", "run_lint", "run_format"):
        assert not _is_coding_task(
            TaskStub(tool, f"run coding {tool}", {"workspace": str(tmp_path)})
        )


def test_write_file_without_path_is_not_sent_to_transaction():
    assert not _is_coding_task(TaskStub("write_file", "write code", {"content": "x=1"}))
