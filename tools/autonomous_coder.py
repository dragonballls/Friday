"""Persistent, bounded background self-coding worker for Friday.

The worker keeps a compact durable state file and checkpoint history so a
crash or interruption does not erase the coding session's working context.
It uses the existing cloud coding provider and confined Autopilot pipeline.
It never installs packages and never pushes to GitHub automatically.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from agent.llm import chat as llm_chat
from core.autopilot import Autopilot
from core.logger import info, warn
from core.planner import Planner
from core.registry import discover_plugins, get_tool_definitions, get_tool_map
from core.security import get_permission_manager

DEFAULT_INTERVAL = 1800
DEFAULT_MAX_RETRIES = 1
STATE_FILE = "autonomous-coder-state.json"
MAX_CONTEXT_CHARS = 8000

_ALLOWED_TOOLS = {
    "read_file",
    "write_file",
    "list_dir",
    "app_coding_checkpoint",
    "run_project_tests",
}


def _workspace() -> Path:
    configured = os.getenv("FRIDAY_WORKSPACE", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    # Prefer the traditional checkout when it exists; packaged installs get a
    # durable per-user workspace that survives app restarts and upgrades.
    checkout = (Path.home() / "Friday").resolve()
    if (checkout / ".git").exists():
        return checkout
    return (Path(os.getenv("LOCALAPPDATA", Path.home())) / "Friday" / "coding-workspace").resolve()


def _state_path(root: Path) -> Path:
    return root / ".friday" / STATE_FILE


def _load_state(root: Path) -> dict:
    path = _state_path(root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(root: Path, state: dict) -> None:
    path = _state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _ensure_workspace(root: Path) -> bool:
    if (root / ".git").exists():
        return True
    root.parent.mkdir(parents=True, exist_ok=True)
    repo = os.getenv("FRIDAY_GITHUB_REPO", "https://github.com/dragonballls/Friday.git")
    try:
        result = subprocess.run(
            ["git", "clone", "--", repo, str(root)],
            cwd=root.parent,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            shell=False,
        )
        return result.returncode == 0 and (root / ".git").exists()
    except (OSError, subprocess.TimeoutExpired):
        return False


def _lock_path(root: Path) -> Path:
    return root / ".friday" / "autonomous-coder.lock"


def _acquire_lock(lock: Path) -> bool:
    try:
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.mkdir()
        (lock / "pid").write_text(str(os.getpid()), encoding="utf-8")
        return True
    except FileExistsError:
        return False


def _release_lock(lock: Path) -> None:
    try:
        pid_file = lock / "pid"
        if pid_file.exists():
            pid_file.unlink()
        lock.rmdir()
    except OSError:
        pass


def _log(root: Path, event: str, **data) -> None:
    record = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": event, **data}
    path = root / ".friday" / "autonomous-coder.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _compact_context(state: dict) -> str:
    prior = str(state.get("context_summary", "")).strip()
    changes = state.get("changed_paths", [])
    last_error = str(state.get("last_error", "")).strip()
    text = (
        "PERSISTENT CODING CONTEXT\n"
        f"Previous session summary: {prior}\n"
        f"Previously changed paths: {', '.join(str(x) for x in changes[-20:])}\n"
        f"Last failure (if any): {last_error}\n"
        "Continue from the current repository state; do not assume prior edits vanished."
    )
    return text[-MAX_CONTEXT_CHARS:]


def run_cycle(root: Path, state: dict) -> bool:
    if not _ensure_workspace(root):
        _log(root, "blocked", reason="persistent workspace could not be initialized")
        return False

    discover_plugins()
    tool_map = get_tool_map()
    tool_defs = get_tool_definitions()
    missing = sorted(_ALLOWED_TOOLS - set(tool_map))
    if missing:
        _log(root, "blocked", missing_tools=missing)
        warn(f"Autonomous coder blocked; missing safe tools: {missing}")
        return False

    # Headless coding may resolve only the confirmation class used by the
    # restricted coding toolset. The tool allowlist still excludes destructive
    # computer-control/network operations.
    get_permission_manager().set_interactive(False)

    planner = Planner(llm_chat, tool_definitions=tool_defs)
    coder_provider = lambda messages, tools=None: llm_chat(
        messages,
        tools=tools,
        provider_name="zen_coder",
    )

    goal = (
        "Work on the Friday repository itself. Make exactly one small, safe, useful code improvement. "
        "First inspect the current source and tests. Create a coding checkpoint. Choose one existing "
        "source file that can be improved without changing public behavior unnecessarily. Implement the "
        "smallest useful change, then run focused existing tests for that area. Do not install packages. "
        "Do not modify .env, secrets, generated installers, Git metadata, or files outside the Friday workspace. "
        "Do not push to GitHub. A reviewed local commit is allowed for crash recovery. "
        "Use the persistent coding context supplied below and continue from the current repository state.\n\n"
        + _compact_context(state)
    )

    auto = Autopilot(
        planner=planner,
        llm_provider=coder_provider,
        tool_map=tool_map,
        tool_definitions=tool_defs,
        workspace=str(root),
        verify=True,
        tool_allowlist=sorted(_ALLOWED_TOOLS),
        max_retries=DEFAULT_MAX_RETRIES,
        confirm_timeout=90.0,
    )

    saw_success = False
    changed_paths: list[str] = []
    last_summary = ""
    last_error = ""
    for event in auto.run(goal, context=[{"role": "system", "content": _compact_context(state)}]):
        _log(root, "event", payload=event)
        if event.get("type") == "autopilot" and event.get("event") == "step_done":
            task = event.get("task") or {}
            last_summary = str(task.get("description") or last_summary)
            if task.get("status") == "failed":
                last_error = str(task.get("error") or "coding step failed")
        elif event.get("type") == "autopilot" and event.get("event") == "done":
            stats = event.get("stats", {})
            saw_success = int(stats.get("completed", 0)) > 0 and int(stats.get("failed", 0)) == 0
            last_summary = str(event.get("summary") or last_summary)
        elif event.get("type") == "coding_transaction" and event.get("status") == "completed":
            changed_paths.extend(str(p) for p in event.get("changed_paths", []) if p)
        elif event.get("type") == "done" and event.get("content"):
            info(f"Autonomous coding cycle finished: {event.get('content', '')}")

    new_state = {
        **state,
        "last_cycle_at": datetime.now(timezone.utc).isoformat(),
        "last_success": saw_success,
        "last_summary": last_summary[:1200],
        "last_error": last_error[:1200],
        "changed_paths": list(dict.fromkeys((state.get("changed_paths", []) + changed_paths)))[-50:],
        "context_summary": (
            f"Last cycle success={saw_success}. {last_summary[:900]} "
            f"Changed paths: {', '.join(changed_paths[-10:])}."
        ).strip(),
    }
    _save_state(root, new_state)
    return saw_success


def main() -> int:
    root = _workspace()
    interval = max(300, int(os.getenv("FRIDAY_AUTONOMOUS_INTERVAL", str(DEFAULT_INTERVAL))))
    enabled = os.getenv("FRIDAY_AUTONOMOUS_CODING", "1").strip().lower() not in {"0", "false", "no", "off"}
    lock = _lock_path(root)

    if not enabled or not _acquire_lock(lock):
        return 0

    try:
        _log(root, "started", workspace=str(root), interval_seconds=interval, pid=os.getpid())
        state = _load_state(root)
        while True:
            started = time.monotonic()
            try:
                run_cycle(root, state)
                state = _load_state(root)
            except Exception as exc:  # defensive worker boundary
                state["last_error"] = str(exc)[:1200]
                state["last_cycle_at"] = datetime.now(timezone.utc).isoformat()
                _save_state(root, state)
                _log(root, "error", error=str(exc))
                warn(f"Autonomous coding cycle failed: {exc}")
            elapsed = time.monotonic() - started
            time.sleep(max(1, interval - elapsed))
    finally:
        _log(root, "stopped")
        _release_lock(lock)


if __name__ == "__main__":
    raise SystemExit(main())
