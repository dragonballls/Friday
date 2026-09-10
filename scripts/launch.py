#!/usr/bin/env python3
"""Start Friday safely and keep live updates in place without browser reloads."""

from __future__ import annotations

import datetime as _dt
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPDATER = ROOT / "scripts" / "update.py"
LOG_DIR = ROOT / "logs"
LAUNCH_LOG = LOG_DIR / "launcher.log"
# Polling every second causes needless network traffic and Git process churn.
# Thirty seconds keeps Friday reasonably fresh while leaving the machine quiet.
AUTO_UPDATE_INTERVAL = 30
STARTUP_TASK_NAME = "Friday UI"
STARTUP_RETRY_DELAY = 5
MAX_STARTUP_RETRY_DELAY = 30


def _log(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().astimezone().isoformat(timespec="seconds")
    with LAUNCH_LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"[{stamp}] {message}\n")
    print(message, file=sys.stderr)


def print_colored(text: str, color_code: str = "37") -> None:
    print(f"\033[{color_code}m{text}\033[0m")


def get_terminal_width() -> int:
    return shutil.get_terminal_size((80, 20)).columns


def _ensure_windows_startup_task() -> None:
    if sys.platform != "win32":
        return
    task_command = subprocess.list2cmdline([sys.executable, str(Path(__file__).resolve()), "--ui", "--startup"])
    result = subprocess.run(
        ["schtasks", "/Create", "/SC", "ONLOGON", "/TN", STARTUP_TASK_NAME, "/TR", task_command, "/F"],
        cwd=ROOT, capture_output=True, text=True, timeout=30, check=False,
    )
    if result.returncode != 0:
        _log(f"Could not register automatic Windows startup for Friday (code {result.returncode}): {result.stderr.strip() or result.stdout.strip()}")
    else:
        _log("Friday Windows startup task is installed for the current user.")


def _detach_windows_ui() -> bool:
    if sys.platform != "win32" or os.environ.get("FRIDAY_DETACHED_UI") == "1" or "--startup" in sys.argv[1:]:
        return False
    detached_process = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
    new_process_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
    env = os.environ.copy()
    env["FRIDAY_DETACHED_UI"] = "1"
    subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "--ui", "--startup"],
        cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        close_fds=True, creationflags=detached_process | new_process_group, env=env,
    )
    return True


def _auto_update_monitor(root: str, update_event: threading.Event, stop_event: threading.Event):
    raw_interval = os.environ.get("FRIDAY_AUTO_UPDATE_INTERVAL", str(AUTO_UPDATE_INTERVAL))
    try:
        interval = max(1, int(raw_interval))
    except ValueError:
        interval = AUTO_UPDATE_INTERVAL
    first_check = True
    while not stop_event.is_set():
        if not first_check and stop_event.wait(interval):
            return
        first_check = False
        try:
            branch = subprocess.run(["git", "branch", "--show-current"], cwd=root, capture_output=True, text=True, timeout=15, check=False).stdout.strip()
            if branch != "main":
                _log(f"Auto-update paused: local checkout is on '{branch or 'detached HEAD'}', not main.")
                continue
            status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=root, capture_output=True, text=True, timeout=15, check=False)
            if status.returncode != 0:
                continue
            if status.stdout.strip():
                _log("Auto-update paused: local changes are present; refusing to overwrite them.")
                continue
            fetch = subprocess.run(["git", "fetch", "origin", "main", "--prune"], cwd=root, capture_output=True, text=True, timeout=60, check=False)
            if fetch.returncode != 0:
                continue
            local = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=15, check=False).stdout.strip()
            remote = subprocess.run(["git", "rev-parse", "origin/main"], cwd=root, capture_output=True, text=True, timeout=15, check=False).stdout.strip()
            if local and remote and local != remote:
                _log(f"Auto-update detected new main: {local[:12]} -> {remote[:12]}.")
                update_event.set()
                return
        except (OSError, subprocess.SubprocessError, ValueError):
            continue


def _start_auto_update_monitor(root: str, update_event: threading.Event, stop_event: threading.Event):
    monitor = threading.Thread(target=_auto_update_monitor, args=(root, update_event, stop_event), name="friday-auto-updater", daemon=True)
    monitor.start()
    return monitor


def _terminate_processes(procs: list[subprocess.Popen]):
    for proc in procs:
        if proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and any(p.poll() is None for p in procs):
        time.sleep(0.2)
    for proc in procs:
        if proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass


def _clear_frontend_port() -> None:
    """Compatibility no-op: never kill an existing Friday/Vite server."""
    return


def _frontend_port_is_ready() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5173), timeout=0.5):
            return True
    except OSError:
        return False


def _wait_for_port(host: str, port: int, proc: subprocess.Popen, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"Friday UI service exited before port {port} became ready (exit code {proc.returncode}).")
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError as exc:
            last_error = exc
        time.sleep(0.25)
    raise RuntimeError(f"Friday UI service did not become ready on {host}:{port} within {timeout:.0f}s ({last_error}).")


def _start_api_process(desktop: str) -> subprocess.Popen:
    proc = subprocess.Popen([sys.executable, os.path.join(desktop, "api_server.py")], cwd=desktop)
    try:
        _wait_for_port("127.0.0.1", 8080, proc)
    except Exception:
        _terminate_processes([proc])
        raise
    return proc


def _restart_api_process(procs: list[subprocess.Popen], desktop: str) -> None:
    """Restart only the backend after an update; keep Vite/browser alive for HMR."""
    old_api = procs[0] if procs else None
    if old_api is not None:
        _terminate_processes([old_api])
    procs[0:1] = [_start_api_process(desktop)]


def _start_ui_processes(desktop: str) -> list[subprocess.Popen]:
    if sys.platform == "win32":
        node_cmd = shutil.which("node.exe") or shutil.which("node")
        vite_js = os.path.join(desktop, "node_modules", "vite", "bin", "vite.js")
        if not node_cmd:
            raise RuntimeError("Node.js was not found on PATH; cannot start the Friday frontend.")
        if not os.path.isfile(vite_js):
            raise RuntimeError(f"Vite entrypoint was not found: {vite_js}")
        front_cmd = [node_cmd, vite_js, "--host", "127.0.0.1"]
    else:
        front_cmd = ["npm", "run", "dev", "--", "--host", "127.0.0.1"]
    procs: list[subprocess.Popen] = []
    try:
        procs.append(_start_api_process(desktop))
        if _frontend_port_is_ready():
            print_colored("Friday UI already running — reusing existing Vite server.", "32")
            return procs
        front = subprocess.Popen(front_cmd, cwd=desktop)
        procs.append(front)
        _wait_for_port("127.0.0.1", 5173, front)
        return procs
    except Exception:
        _terminate_processes(procs)
        raise


def _open_ui_browser():
    url = "http://127.0.0.1:5173/"
    print_colored(f"Friday UI ready — opening {url}", "32")
    webbrowser.open(url)


def _recover_dead_processes(procs: list[subprocess.Popen], desktop: str) -> None:
    """Recover only failed services so one failure cannot take down the other."""
    if len(procs) >= 1 and procs[0].poll() is not None:
        procs[0:1] = [_start_api_process(desktop)]
    if len(procs) >= 2 and procs[1].poll() is not None:
        if sys.platform == "win32":
            node_cmd = shutil.which("node.exe") or shutil.which("node")
            vite_js = os.path.join(desktop, "node_modules", "vite", "bin", "vite.js")
            if not node_cmd or not os.path.isfile(vite_js):
                raise RuntimeError("Vite entrypoint is unavailable during frontend recovery.")
            front_cmd = [node_cmd, vite_js, "--host", "127.0.0.1"]
        else:
            front_cmd = ["npm", "run", "dev", "--", "--host", "127.0.0.1"]
        if _frontend_port_is_ready():
            print_colored("Friday UI already running — keeping existing Vite server.", "32")
            return
        front = subprocess.Popen(front_cmd, cwd=desktop)
        _wait_for_port("127.0.0.1", 5173, front)
        procs[1:2] = [front]


def _launch_ui():
    """Keep the existing browser page alive while source updates arrive through Vite HMR."""
    root = str(ROOT)
    desktop = os.path.join(root, "desktop")
    print_colored("Friday desktop UI starting…", "36")
    retry_delay = STARTUP_RETRY_DELAY
    browser_opened = False

    while True:
        update_event = threading.Event()
        stop_event = threading.Event()
        _start_auto_update_monitor(root, update_event, stop_event)
        procs: list[subprocess.Popen] = []
        try:
            procs = _start_ui_processes(desktop)
            retry_delay = STARTUP_RETRY_DELAY
            if not browser_opened:
                _open_ui_browser()
                browser_opened = True

            while True:
                time.sleep(1.0)
                if update_event.is_set():
                    print_colored("\nFriday update detected — applying in place; browser will stay open…", "33")
                    stop_event.set()
                    result = _run_update(build=False)
                    if result == 0:
                        try:
                            _restart_api_process(procs, desktop)
                            print_colored("Friday updated in place. Frontend changes are handed to Vite HMR; no browser reopen.", "32")
                        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                            _log(f"Backend hot-restart failed; keeping Friday alive: {exc}")
                    else:
                        _log("Live update was not applied; keeping the current Friday session running.")
                    update_event.clear()
                    stop_event.clear()
                    _start_auto_update_monitor(root, update_event, stop_event)
                elif any(p.poll() is not None for p in procs):
                    print_colored("\nFriday service stopped — recovering only the failed service…", "33")
                    _recover_dead_processes(procs, desktop)
        except KeyboardInterrupt:
            print_colored("\nShutting down Friday UI…", "33")
            stop_event.set()
            _terminate_processes(procs)
            return
        except RuntimeError as exc:
            _log(f"Friday UI startup/recovery failed: {exc}")
            stop_event.set()
            _terminate_processes(procs)
            print_colored(f"Friday UI will retry automatically in {retry_delay}s instead of exiting.", "33")
            time.sleep(retry_delay)
            retry_delay = min(MAX_STARTUP_RETRY_DELAY, retry_delay * 2)
        finally:
            stop_event.set()
            _terminate_processes(procs)


def main():
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, ValueError):
                pass
    args = sys.argv[1:]
    if "--ui" in args and sys.platform == "win32" and "--startup" not in args:
        _ensure_windows_startup_task()
    if "--ui" in args and _detach_windows_ui():
        print_colored("Friday UI detached — it will keep running after this PowerShell window closes.", "32")
        return 0
    if "--ui" in args:
        _run_update(build=True)
        _launch_ui()
        return 0
    return subprocess.run([sys.executable, str(ROOT / "main.py"), *args], cwd=ROOT, check=False).returncode


def _run_update(*, build: bool = False) -> int:
    command = [sys.executable, str(UPDATER)]
    if build:
        command.append("--build")
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode not in (0, 2, 3, 4):
        _log(f"Friday update failed (code {result.returncode}); keeping current checkout.")
    elif result.returncode in (2, 4):
        _log("Friday update was skipped because the local checkout is not safely fast-forwardable; using current checkout.")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())