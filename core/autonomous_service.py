"""Persistent, cloud-first autonomous coding service for the Friday desktop app.

The service maintains a small durable state file and rolling context summary so a
restart does not require replaying an unbounded conversation. Coding is confined
to a dedicated Git workspace and a small allowlist of coding/verification tools.
Verification prompts raised by that allowlist are approved automatically by this
service; it never auto-approves arbitrary desktop-control or destructive tools.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from agent.llm import chat as llm_chat
from core.autopilot import Autopilot
from core.planner import Planner
from core.registry import discover_plugins, get_tool_definitions, get_tool_map
from core.security import get_approval_registry

REMOTE = "https://github.com/dragonballls/Friday.git"
INTERVAL_SECONDS = max(300, int(os.getenv("FRIDAY_AUTONOMOUS_INTERVAL", "900")))
BRANCH = os.getenv("FRIDAY_AUTONOMOUS_BRANCH", "feat/tauri-desktop-app").strip()
SAFE_TOOLS = {
    "read_file",
    "write_file",
    "list_dir",
    "app_coding_checkpoint",
    "run_project_tests",
    "git_commit_changes",
}
MAX_HISTORY = 12


def workspace() -> Path:
    configured = os.getenv("FRIDAY_WORKSPACE", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    home = Path.home()
    candidates = [
        home / "Friday",
        home / "Documents" / "Friday",
        home / "Desktop" / "Friday",
    ]
    for candidate in candidates:
        if (candidate / ".git").exists():
            return candidate.resolve()
    local_app_data = Path(os.getenv("LOCALAPPDATA", str(home)))
    return (local_app_data / "Friday" / "coding-workspace").resolve()


def state_path(root: Path) -> Path:
    return root / ".friday" / "autonomous-state.json"


def lock_path(root: Path) -> Path:
    return root / ".friday" / "autonomous-coder.lock"


def load_state(root: Path) -> dict:
    path = state_path(root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, ValueError, TypeError):
        pass
    return {
        "version": 1,
        "cycle": 0,
        "status": "new",
        "history": [],
        "last_changed_paths": [],
        "last_error": "",
        "context_summary": "No previous autonomous coding cycle has completed.",
    }


def save_state(root: Path, state: dict) -> None:
    path = state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def log(root: Path, event: str, **details) -> None:
    record = {"timestamp": datetime.now(UTC).isoformat(), "event": event, **details}
    path = root / ".friday" / "autonomous-coder.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def ensure_workspace(root: Path) -> bool:
    root.parent.mkdir(parents=True, exist_ok=True)
    if (root / ".git").exists():
        return True
    if any(root.iterdir()):
        log(root, "workspace_blocked", reason="non-empty directory is not a Git repository")
        return False
    args = ["git", "clone", "--depth", "1"]
    if BRANCH:
        args += ["--branch", BRANCH]
    args += [REMOTE, str(root)]
    try:
        result = subprocess.run(args, cwd=root.parent, capture_output=True, text=True, timeout=300, shell=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        log(root, "clone_failed", error=str(exc))
        return False
    if result.returncode != 0:
        log(root, "clone_failed", error=result.stderr[-2000:], exit_code=result.returncode)
        return False
    return True


def acquire_lock(path: Path) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.mkdir()
        (path / "pid").write_text(str(os.getpid()), encoding="utf-8")
        return True
    except FileExistsError:
        return False


def release_lock(path: Path) -> None:
    try:
        (path / "pid").unlink(missing_ok=True)
        path.rmdir()
    except OSError:
        pass


def filtered_definitions(definitions: list[dict]) -> list[dict]:
    result = []
    for definition in definitions:
        fn = definition.get("function", definition)
        if fn.get("name") in SAFE_TOOLS:
            result.append(definition)
    return result


def context_for(state: dict) -> list[dict]:
    history = state.get("history", [])[-MAX_HISTORY:]
    compact = {
        "cycle": state.get("cycle", 0),
        "status": state.get("status", "unknown"),
        "last_changed_paths": state.get("last_changed_paths", []),
        "last_error": state.get("last_error", ""),
        "history": history,
    }
    text = json.dumps(compact, ensure_ascii=False)
    if len(text) > 6000:
        text = text[-6000:]
    return [
        {
            "role": "system",
            "content": (
                "PERSISTED AUTONOMOUS CODING CONTEXT. Continue from this durable state; "
                "do not assume previous context is available. Keep new work small and build on "
                "verified changes already present in the workspace.\n" + text
            ),
        }
    ]


def commit_verified_changes(root: Path, cycle: int) -> str:
    try:
        subprocess.run(["git", "add", "-A", "--", "."], cwd=root, check=True, timeout=30, shell=False)
        result = subprocess.run(
            ["git", "commit", "-m", f"chore: autonomous Friday improvement cycle {cycle}"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=60,
            shell=False,
        )
        if result.returncode == 0:
            return "committed"
        combined = (result.stdout + "\n" + result.stderr).lower()
        return "clean" if "nothing to commit" in combined else "commit_failed"
    except (OSError, subprocess.SubprocessError):
        return "commit_failed"


def run_cycle(root: Path, state: dict) -> bool:
    discover_plugins()
    tool_map = get_tool_map()
    tool_defs = filtered_definitions(get_tool_definitions())
    missing = sorted(SAFE_TOOLS - set(tool_map))
    if missing:
        state["status"] = "blocked"
        state["last_error"] = "Missing safe tools: " + ", ".join(missing)
        log(root, "blocked", missing=missing)
        save_state(root, state)
        return False

    planner = Planner(llm_chat, tool_definitions=tool_defs)
    coder_provider = lambda messages, tools=None: llm_chat(messages, tools=tools, provider_name="zen_coder")
    auto = Autopilot(
        planner=planner,
        llm_provider=coder_provider,
        tool_map=tool_map,
        tool_definitions=tool_defs,
        workspace=str(root),
        verify=True,
        tool_allowlist=sorted(SAFE_TOOLS),
        max_retries=3,
        confirm_timeout=90.0,
    )

    goal = (
        "Continue improving the Friday repository itself. Inspect the persisted context and current "
        "workspace first. Make exactly one small, useful coding improvement. Create a checkpoint before "
        "editing. Use only the available safe coding tools. Run the most relevant existing tests after "
        "editing. Preserve previous verified work, avoid package installation, secrets, generated installers, "
        "and unrelated files. Do not push to a remote. The change is complete only when verification passes."
    )

    registry = get_approval_registry()
    completed = False
    changed_paths: list[str] = []
    last_error = ""
    for event in auto.run(goal, context=context_for(state)):
        log(root, "event", payload=event)
        if event.get("type") == "requires_confirmation":
            # The worker only exposes SAFE_TOOLS, so these approvals are limited to
            # filesystem/checkpoint/test operations in the confined coding workspace.
            registry.resolve(str(event.get("request_id", "")), True)
        elif event.get("type") == "autopilot" and event.get("event") == "step_done":
            task = event.get("task", {})
            if task.get("status") == "completed":
                completed = True
            changed_paths.extend(event.get("verification", {}).get("changed_paths", []) or [])
            last_error = str(task.get("error") or last_error)
        elif event.get("type") == "autopilot" and event.get("event") == "done":
            stats = event.get("stats", {})
            completed = int(stats.get("completed", 0)) > 0 and int(stats.get("failed", 0)) == 0
        elif event.get("type") == "done" and event.get("final") and "stopped" in str(event.get("content", "")).lower():
            last_error = str(event.get("content", ""))

    if completed:
        commit_result = commit_verified_changes(root, state["cycle"])
        state["status"] = "completed"
        state["last_error"] = ""
        state["last_changed_paths"] = sorted(set(changed_paths))[-50:]
        summary = f"Cycle {state['cycle']} completed; local persistence result: {commit_result}."
        state.setdefault("history", []).append({"cycle": state["cycle"], "result": "completed", "summary": summary})
        state["history"] = state["history"][-MAX_HISTORY:]
        state["context_summary"] = summary
        save_state(root, state)
        log(root, "completed", commit=commit_result, changed_paths=state["last_changed_paths"])
        return True

    state["status"] = "failed"
    state["last_error"] = last_error or "Autonomous coding cycle did not pass completion gates."
    state.setdefault("history", []).append({"cycle": state["cycle"], "result": "failed", "summary": state["last_error"][:500]})
    state["history"] = state["history"][-MAX_HISTORY:]
    save_state(root, state)
    log(root, "failed", error=state["last_error"])
    return False


def run_forever() -> None:
    root = workspace()
    if not ensure_workspace(root):
        return
    lock = lock_path(root)
    if not acquire_lock(lock):
        return
    try:
        state = load_state(root)
        log(root, "started", workspace=str(root), interval=INTERVAL_SECONDS, pid=os.getpid())
        while True:
            state["cycle"] = int(state.get("cycle", 0)) + 1
            state["status"] = "running"
            state["last_error"] = ""
            save_state(root, state)
            started = time.monotonic()
            try:
                run_cycle(root, state)
            except Exception as exc:  # defensive boundary: never take down Friday
                state["status"] = "error"
                state["last_error"] = str(exc)
                save_state(root, state)
                log(root, "error", error=str(exc))
            elapsed = time.monotonic() - started
            time.sleep(max(1.0, INTERVAL_SECONDS - elapsed))
    finally:
        release_lock(lock)
        log(root, "stopped")
