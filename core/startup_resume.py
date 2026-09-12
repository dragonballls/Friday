from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()


def state_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or Path.home()) / "Friday"
    else:
        base = Path(os.environ.get("XDG_STATE_HOME") or (Path.home() / ".local" / "state")) / "Friday"
    base.mkdir(parents=True, exist_ok=True)
    return base / "task_state.json"


def _read() -> dict[str, Any]:
    try:
        with state_path().open("r", encoding="utf-8") as f:
            value = json.load(f)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def save_state(**updates: Any) -> dict[str, Any]:
    with _LOCK:
        state = _read()
        state.update(updates)
        state["updated_at"] = time.time()
        path = state_path()
        fd, tmp = tempfile.mkstemp(prefix="task_state.", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        finally:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass
        return state


def get_state() -> dict[str, Any]:
    with _LOCK:
        return _read()


def begin_task(goal: str, workspace: str) -> None:
    save_state(status="running", goal=goal, workspace=workspace, checkpoint=None)


def checkpoint(event: dict[str, Any]) -> None:
    save_state(status="running", checkpoint=event)


def finish_task(status: str, **extra: Any) -> None:
    save_state(status=status, **extra)


def unfinished_task() -> dict[str, Any] | None:
    state = get_state()
    if state.get("status") == "running" and state.get("goal") and state.get("workspace"):
        return state
    return None
