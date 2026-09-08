from core.planner import _toolcalls_to_tasks


def test_tool_call_json_arguments_are_preserved():
    tasks = _toolcalls_to_tasks(
        [
            {
                "id": "call-1",
                "function": {
                    "name": "write_file",
                    "arguments": '{"path":"feature.py","content":"hello"}',
                },
            }
        ]
    )

    assert len(tasks) == 1
    assert tasks[0].tool == "write_file"
    assert tasks[0].args == {"path": "feature.py", "content": "hello"}


def test_invalid_tool_call_arguments_fail_closed_to_empty_dict():
    tasks = _toolcalls_to_tasks(
        [
            {
                "id": "call-1",
                "function": {
                    "name": "write_file",
                    "arguments": "not-json",
                },
            }
        ]
    )

    assert tasks[0].args == {}
