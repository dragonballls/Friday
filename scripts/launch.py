#!/usr/bin/env python3
"""Start Friday safely, keeping the desktop UI synchronized with GitHub."""

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
AUTO_UPDATE_INTERVAL = 1
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
    """Register Friday to start automatically whenever the current user logs in."""
    if sys.platform != "win32":
        return

    task_command = subprocess.list2cmdline(
        [sys.executable, str(Path(__file__).resolve()), "--ui", "--startup"]
    )
    result = subprocess.run(
        ["schtasks", "/Create", "/SC", "ONLOGON", "/TN", STARTUP_TASK_NAME, "/TR", task_command, "/F"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        _log(
            "Could not register automatic Windows startup for Friday "
            f"(code {result.returncode}): {result.stderr.strip() or result.stdout.strip()}"
        )
    else:
        _log("Friday Windows startup task is installed for the current user.")


def _detach_windows_ui() -> bool:
    """Re-launch the UI supervisor without tying it to the current console."""
    if (
        sys.platform != "win32"
        or os.environ.get("FRIDAY_DETACHED_UI") == "1"
        or "--startup" in sys.argv[1:]
    ):
        return False

    detached_process = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
    new_process_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
    env = os.environ.copy()
    env["FRIDAY_DETACHED_UI"] = "1"
    subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "--ui", "--startup"],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=detached_process | new_process_group,
        env=env,
    )
    return True


def _auto_update_monitor(root: str, update_event: threading.Event, stop_event: threading.Event):
    """Watch origin/main while the UI supervisor is alive."""
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
            branch = subprocess.run(
                ["git", "branch", "--show-current"], cwd=root, capture_output=True, text=True, timeout=15, check=False
            ).stdout.strip()
            if branch != "main":
                _log(f"Auto-update paused: local checkout is on '{branch or 'detached HEAD'}', not main.")
                continue
            status = subprocess.run(
                ["git", "status", "--porcelain", "--untracked-files=all"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if status.returncode != 0:
                continue
            if status.stdout.strip():
                _log("Auto-update paused: local changes are present; refusing to overwrite them.")
                continue
            fetch = subprocess.run(
                ["git", "fetch", "origin", "main", "--prune"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            if fetch.returncode != 0:
                continue
            local = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=15, check=False
            ).stdout.strip()
            remote = subprocess.run(
                ["git", "rev-parse", "origin/main"], cwd=root, capture_output=True, text=True, timeout=15, check=False
            ).stdout.strip()
            if local and remote and local != remote:
                _log(f"Auto-update detected new main: {local[:12]} -> {remote[:12]}.")
                update_event.set()
                return
        except (OSError, subprocess.SubprocessError, ValueError):
            continue


def _start_auto_update_monitor(root: str, update_event: threading.Event, stop_event: threading.Event):
    monitor = threading.Thread(
        target=_auto_update_monitor, args=(root, update_event, stop_event), name="friday-auto-updater", daemon=True
    )
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
    """Kill only a Windows listener on Vite's frontend port before starting it."""
    if sys.platform != "win32":
        return
    try:
        result = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return
    if result.returncode != 0:
        return
    pids: set[str] = set()
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0].upper() != "TCP":
            continue
        if parts[3].upper() != "LISTENING":
            continue
        if parts[1].rsplit(":", 1)[-1] == "5173" and parts[4].isdigit():
            pids.add(parts[4])
    for pid in pids:
        subprocess.run(
            ["taskkill", "/PID", pid, "/T", "/F"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )


def _wait_for_port(host: str, port: int, proc: subprocess.Popen, timeout: float = 30.0) -> None:
    """Wait until a child service accepts connections, or fail with its exit code."""
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(
                f"Friday UI service exited before port {port} became ready (exit code {proc.returncode})."
            )
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError as exc:
            last_error = exc
        time.sleep(0.25)
    raise RuntimeError(f"Friday UI service did not become ready on {host}:{port} within {timeout:.0f}s ({last_error}).")


def _start_ui_processes(desktop: str) -> list[subprocess.Popen]:
    api_cmd = [sys.executable, os.path.join(desktop, "api_server.py")]
    if sys.platform == "win32":
        npm_cmd = shutil.which("npm.cmd") or shutil.which("npm")
        if not npm_cmd:
            raise RuntimeError("npm was not found on PATH; cannot start the Friday frontend.")
        front_cmd = [npm_cmd, "run", "dev", "--", "--host", "127.0.0.1"]
    else:
        front_cmd = ["npm", "run", "dev", "--", "--host", "127.0.0.1"]

    procs: list[subprocess.Popen] = []
    try:
        api = subprocess.Popen(api_cmd, cwd=desktop)
        procs.append(api)
        _wait_for_port("127.0.0.1", 8080, api)

        _clear_frontend_port()
        front = subprocess.Popen(front_cmd, cwd=desktop)
        procs.append(front)
        _wait_for_port("127.0.0.1", 5173, front)
        return procs
    except Exception:
        _terminate_processes(procs)
        raise


def _open_ui_browser():
    """Open the actual Vite frontend, not the API's default port."""
    url = "http://127.0.0.1:5173/"
    print_colored(f"Friday UI ready — opening {url}", "32")
    webbrowser.open(url)


def _launch_ui():
    """Launch the UI and keep its source/runtime synchronized with origin/main."""
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
                    print_colored("\nFriday update detected — restarting safely…", "33")
                    _terminate_processes(procs)
                    procs.clear()
                    result = subprocess.run(
                        [sys.executable, os.path.join(root, "scripts", "update.py"), "--build"], cwd=root, check=False
                    )
                    if result.returncode == 0:
                        stop_event.set()
                        os.execv(sys.executable, [sys.executable, *sys.argv])
                    _log("Update could not be fully applied; restarting Friday on the latest source available.")
                    update_event.clear()
                    stop_event.clear()
                    _start_auto_update_monitor(root, update_event, stop_event)
                    procs = _start_ui_processes(desktop)
                elif any(p.poll() is not None for p in procs):
                    print_colored(
                        "\nFriday UI process stopped — restarting the UI while keeping update monitoring active.", "33"
                    )
                    _terminate_processes(procs)
                    procs.clear()
                    time.sleep(2.0)
                    procs = _start_ui_processes(desktop)
        except KeyboardInterrupt:
            print_colored("\nShutting down Friday UI…", "33")
            stop_event.set()
            _terminate_processes(procs)
            return
        except RuntimeError as exc:
            _log(f"Friday UI startup/recovery failed: {exc}")
            stop_event.set()
            _terminate_processes(procs)
            print_colored(
                f"Friday UI will retry automatically in {retry_delay}s instead of exiting.", "33"
            )
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


def _run_update(*, build: bool = False) -> None:
    """Synchronize the clean main checkout before startup; never make it fatal."""
    command = [sys.executable, str(UPDATER)]
    if build:
        command.append("--build")
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode not in (0, 2, 3, 4):
        _log(f"Friday update failed (code {result.returncode}); launching current checkout.")
    elif result.returncode in (2, 4):
        _log("Friday update was skipped because the local checkout is not safely fast-forwardable; using current checkout.")


if __name__ == "__main__":
    raise SystemExit(main())
