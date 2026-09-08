import json

from core.executor import Executor
from core.planner import Task


def _llm(*responses):
    calls = iter(responses)

    def provider(*args, **kwargs):
        return iter(next(calls))

    return provider


def _tool_call(name, args, call_id="call"):
    return {
        "id": call_id,
        "function": {"name": name, "arguments": json.dumps(args)},
    }


def test_coding_task_requires_implementation_and_verification():
    task = Task(id="coding-1", description="coding change")
    tool_map = {
        "write_file": lambda **kwargs: {"success": True},
        "verify_coding_change": lambda **kwargs: {
            "success": True,
            "all_gates_passed": True,
        },
    }
    llm = _llm(
        [{"type": "done", "content": "", "tool_calls": [_tool_call("write_file", {"path": "feature.py", "content": "x=1"})]}],
        [{"type": "done", "content": "", "tool_calls": [_tool_call("verify_coding_change", {"workspace": "."})]}],
        [{"type": "done", "content": "completed", "tool_calls": None}],
    )

    results = list(Executor(llm, tool_map).execute_task(task, [], [], max_iterations=5))

    assert task.status == "completed"
    assert results[-1]["type"] == "done"


def test_coding_task_fails_closed_without_verification():
    task = Task(id="coding-2", description="coding change")
    tool_map = {
        "write_file": lambda **kwargs: {"success": True},
    }
    llm = _llm(
        [{"type": "done", "content": "", "tool_calls": [_tool_call("write_file", {"path": "feature.py", "content": "x=1"})]}],
        [{"type": "done", "content": "finished", "tool_calls": None}],
    )

    results = list(Executor(llm, tool_map).execute_task(task, [], [], max_iterations=5))

    assert task.status == "failed"
    assert "verification" in task.error.lower()
    assert results[-1]["type"] == "done"
    assert results[-1]["final"] is True
