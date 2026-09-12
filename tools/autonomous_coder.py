"""Bounded, background self-coding worker for the Friday workspace.

The worker is intentionally conservative: one maintenance cycle at a time,
workspace-confined tools only, no package installation, no git push/commit,
and a long cooldown between cycles. It uses the existing cloud-first coding
provider and the existing Autopilot verification pipeline.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from agent.llm import chat as llm_chat
from core.autopilot import Autopilot
from core.logger import info, warn
from core.planner import Planner
from core.registry import discover_plugins, get_tool_definitions, get_tool_map

DEFAULT_INTERVAL = 1800
DEFAULT_MAX_RETRIES = 1

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
    return (Path.home() / "Friday").resolve()


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
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **data,
    }
    path = root / ".friday" / "autonomous-coder.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_cycle(root: Path) -> bool:
    if not root.is_dir():
        warn(f"Autonomous coder workspace does not exist: {root}")
        return False

    discover_plugins()
    tool_map = get_tool_map()
    tool_defs = get_tool_definitions()
    missing = sorted(_ALLOWED_TOOLS - set(tool_map))
    if missing:
        _log(root, "blocked", missing_tools=missing)
        warn(f"Autonomous coder blocked; missing safe tools: {missing}")
        return False

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
        "smallest useful change, then run the focused existing test(s) for that area. Do not install packages. "
        "Do not modify .env, secrets, generated installers, Git metadata, or files outside the Friday workspace. "
        "Do not commit or push. Stop after the first successful improvement or after a single failed attempt."
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
    for event in auto.run(goal, context=[]):
        _log(root, "event", payload=event)
        if event.get("type") == "autopilot" and event.get("event") == "done":
            stats = event.get("stats", {})
            saw_success = int(stats.get("completed", 0)) > 0 and int(stats.get("failed", 0)) == 0
        elif event.get("type") == "done":
            info(f"Autonomous coding cycle finished: {event.get('content', '')}")

    return saw_success


def main() -> int:
    root = _workspace()
    interval = max(300, int(os.getenv("FRIDAY_AUTONOMOUS_INTERVAL", str(DEFAULT_INTERVAL))))
    enabled = os.getenv("FRIDAY_AUTONOMOUS_CODING", "1").strip().lower() not in {"0", "false", "no", "off"}
    lock = _lock_path(root)

    if not enabled:
        return 0
    if not _acquire_lock(lock):
        return 0

    try:
        _log(root, "started", workspace=str(root), interval_seconds=interval, pid=os.getpid())
        while True:
            started = time.monotonic()
            try:
                run_cycle(root)
            except Exception as exc:  # pragma: no cover - defensive boundary
                _log(root, "error", error=str(exc))
                warn(f"Autonomous coding cycle failed: {exc}")
            elapsed = time.monotonic() - started
            time.sleep(max(1, interval - elapsed))
    finally:
        _log(root, "stopped")
        _release_lock(lock)


if __name__ == "__main__":
    raise SystemExit(main())
