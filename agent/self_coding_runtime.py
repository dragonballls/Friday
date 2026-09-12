from __future__ import annotations

from collections.abc import Generator

from agent.core import _is_coding_task

_MUTATION_TOOLS = {"write_file", "create_file", "save_file"}
_SELF_CODING_MARKERS = (
    "self-cod",
    "build itself",
    "improv",
    "refactor itself",
    "maintain itself",
)


def is_self_coding_goal(goal: str) -> bool:
    lowered = goal.lower()
    return any(marker in lowered for marker in _SELF_CODING_MARKERS)


def is_mutation_task(task) -> bool:
    if getattr(task, "tool", None) in _MUTATION_TOOLS:
        return True
    return _is_coding_task(task)


def run_self_coding(agent, goal: str, workspace: str | None = None) -> Generator[dict, None, None]:
    """Run autonomous self-coding through the safe coding controller.

    Every source mutation is routed through Agent._execute_coding_task so it
    receives path authorization, durable transaction handling, rollback, real
    repository verification, and the bounded repair loop. Non-mutating tasks
    may still use the normal executor for exploration or reasoning.
    """
    if workspace:
        agent.set_output_dir(workspace)

    context = list(agent.messages)
    tasks = agent._planner.create_plan(goal, context=context)
    yield {
        "type": "autopilot",
        "event": "plan",
        "goal": goal,
        "tasks": [task.to_dict() for task in tasks],
        "summary": f"Planned {len(tasks)} self-coding steps.",
    }

    completed = 0
    failed = 0

    for task in tasks:
        yield {"type": "autopilot", "event": "step_start", "task": task.to_dict()}

        if is_mutation_task(task):
            expected_paths = []
            args = getattr(task, "args", None)
            if isinstance(args, dict) and isinstance(args.get("path"), str) and args.get("path"):
                expected_paths.append(args["path"])

            if not expected_paths:
                task.status = "failed"
                task.error = "Self-coding mutation task requires an explicit authorized path."
                yield {"type": "autopilot", "event": "step_done", "task": task.to_dict(), "verification": {"verified": False, "mode": "authorization"}}
                yield {"type": "done", "content": task.error, "final": True}
                return

            for event in agent._execute_coding_task(
                task,
                max_iterations=10,
                expected_paths=expected_paths,
            ):
                yield event
        else:
            agent._executor.output_dir = agent.output_dir
            for event in agent._executor.execute_task(
                task,
                context,
                agent._tool_defs,
            ):
                yield event

        if task.status == "failed":
            failed += 1
            yield {
                "type": "autopilot",
                "event": "step_done",
                "task": task.to_dict(),
                "verification": {"verified": False, "mode": "coding_controller" if is_mutation_task(task) else "executor"},
            }
            yield {"type": "done", "content": f"Self-coding stopped: {task.error or task.description}", "final": True}
            return

        completed += 1
        yield {
            "type": "autopilot",
            "event": "step_done",
            "task": task.to_dict(),
            "verification": {"verified": True, "mode": "safe_coding" if is_mutation_task(task) else "executor"},
        }

    summary = f"Self-coding finished: {completed} completed, {failed} failed."
    yield {"type": "autopilot", "event": "done", "goal": goal, "stats": {"total": len(tasks), "completed": completed, "failed": failed, "skipped": 0}, "summary": summary}
    yield {"type": "done", "content": summary, "final": True}
