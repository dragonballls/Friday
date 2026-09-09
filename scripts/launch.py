#!/usr/bin/env python3
"""Start Friday safely, keeping the desktop UI synchronized with GitHub."""

from __future__ import annotations

import datetime as _dt
import os
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UPDATER = ROOT / "scripts" / "update.py"
MAIN = ROOT / "main.py"
LOG_DIR = ROOT / "logs"
LAUNCH_LOG = LOG_DIR / "launcher.log"


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


def _detach_windows_ui() -> bool:
    """Re-launch the UI supervisor without tying it to the current console."""
    if sys.platform != "win32" or os.environ.get("FRIDAY_DETACHED_UI") == "1":
        return False

    detached_process = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
    new_process_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
    env = os.environ.copy()
    env["FRIDAY_DETACHED_UI"] = "1"
    command = [sys.executable, str(Path(__file__).resolve()), "--ui"]
    subprocess.Popen(
        command,
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=detached_process | new_process_group,
        env=env,
    )
    return True


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


def _terminate_processes(procs: list[subprocess.Popen]) -> None:
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
            import socket
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

        front = subprocess.Popen(front_cmd, cwd=desktop)
        procs.append(front)
        _wait_for_port("127.0.0.1", 5173, front)
        return procs
    except Exception:
        _terminate_processes(procs)
        raise


def _open_ui_browser() -> None:
    url = "http://127.0.0.1:5173/"
    print_colored(f"Friday UI ready — opening {url}", "32")
    webbrowser.open(url)


def _launch_ui() -> None:
    """Launch the UI and keep its source/runtime synchronized with origin/main."""
    root = os.path.dirname(os.path.abspath(__file__))
    desktop = os.path.join(root, "desktop")
    print_colored("Friday desktop UI starting…", "36")
    update_event = __import__("threading").Event()
    stop_event = __import__("threading").Event()
    procs: list[subprocess.Popen] = []
    try:
        procs = _start_ui_processes(desktop)
        _open_ui_browser()
        while True:
            time.sleep(1.0)
            if update_event.is_set():
                _terminate_processes(procs)
                procs.clear()
                result = subprocess.run(
                    [sys.executable, os.path.join(root, "scripts", "update.py"), "--build"], cwd=root, check=False
                )
                if result.returncode == 0:
                    stop_event.set()
                    os.execv(sys.executable, [sys.executable, *sys.argv])
                update_event.clear()
                stop_event.clear()
                procs = _start_ui_processes(desktop)
                _open_ui_browser()
            elif any(p.poll() is not None for p in procs):
                _terminate_processes(procs)
                procs.clear()
                time.sleep(2.0)
                procs = _start_ui_processes(desktop)
                _open_ui_browser()
    except KeyboardInterrupt:
        print_colored("\nShutting down Friday UI…", "33")
    except RuntimeError as exc:
        print_colored(f"\nFriday UI startup failed: {exc}", "31")
    finally:
        stop_event.set()
        _terminate_processes(procs)


def main() -> int:
    args = sys.argv[1:]

    if "--ui" in args and _detach_windows_ui():
        print_colored("Friday UI detached — it will keep running after this PowerShell window closes.", "32")
        return 0

    if "--ui" in args:
        _run_update(build=True)
    else:
        _run_update()

    if "--ui" not in args:
        return subprocess.run([sys.executable, str(MAIN), *args], cwd=ROOT, check=False).returncode

    attempt = 0
    while True:
        attempt += 1
        _log(f"Starting Friday desktop supervisor (attempt {attempt}).")
        try:
            result = subprocess.run([sys.executable, str(MAIN), *args], cwd=ROOT, check=False)
        except KeyboardInterrupt:
            _log("Friday desktop launcher stopped by user.")
            return 0

        if result.returncode == 0:
            _log("Friday desktop supervisor exited normally.")
            return 0

        _log(f"Friday desktop supervisor exited with code {result.returncode}; retrying in 2 seconds.")
        try:
            time.sleep(2.0)
        except KeyboardInterrupt:
            _log("Friday desktop launcher stopped by user.")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
