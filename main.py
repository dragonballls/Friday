import argparse
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser

from agent.core import Agent
from core.registry import discover_plugins
from voice import is_voice_available, listen, speak

BANNER = r"""
  _____  _     _     _
 |  ___(_) __| |_   _| | ___
 | |_  | |/ _` | | | | |/ _ \
 |  _| | | (_| | |_| | |  __/
 |_|   |_|\__,_|\__,_| |\___|
                |___/
"""
LANG_LABELS = {"english": "English", "hinglish": "Hinglish"}
AUTO_UPDATE_INTERVAL = 60


def get_terminal_width() -> int:
    return shutil.get_terminal_size((80, 20)).columns


def print_colored(text: str, color_code: str = "37"):
    print(f"\033[{color_code}m{text}\033[0m")


def _auto_update_monitor(root: str, update_event: threading.Event, stop_event: threading.Event):
    """Watch origin/main while the UI supervisor is alive."""
    raw_interval = os.environ.get("FRIDAY_AUTO_UPDATE_INTERVAL", str(AUTO_UPDATE_INTERVAL))
    try:
        interval = max(15, int(raw_interval))
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
                continue
            status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=root, capture_output=True, text=True, timeout=15, check=False)
            if status.returncode != 0 or status.stdout.strip():
                continue
            fetch = subprocess.run(["git", "fetch", "origin", "main", "--prune"], cwd=root, capture_output=True, text=True, timeout=60, check=False)
            if fetch.returncode != 0:
                continue
            local = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=15, check=False).stdout.strip()
            remote = subprocess.run(["git", "rev-parse", "origin/main"], cwd=root, capture_output=True, text=True, timeout=15, check=False).stdout.strip()
            if local and remote and local != remote:
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


def _wait_for_port(host: str, port: int, proc: subprocess.Popen, timeout: float = 30.0) -> None:
    """Wait until a child service accepts connections, or fail with its exit code."""
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


def _start_ui_processes(desktop: str) -> list[subprocess.Popen]:
    api_cmd = [sys.executable, os.path.join(desktop, "api_server.py")]
    if sys.platform == "win32":
        npm_cmd = shutil.which("npm.cmd") or shutil.which("npm")
        if not npm_cmd:
            raise RuntimeError("npm was not found on PATH; cannot start the Friday frontend.")
        # Vite may resolve localhost to IPv6 (::1) on Windows. Bind explicitly to
        # IPv4 so the readiness probe and browser use the same reachable endpoint.
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


def _open_ui_browser():
    """Open the actual Vite frontend, not the API's default port."""
    url = "http://127.0.0.1:5173/"
    print_colored(f"Friday UI ready — opening {url}", "32")
    webbrowser.open(url)


def _launch_ui():
    """Launch the UI and keep its source/runtime synchronized with origin/main."""
    root = os.path.dirname(os.path.abspath(__file__))
    desktop = os.path.join(root, "desktop")
    print_colored(BANNER, "36")
    print_colored("─" * get_terminal_width(), "90")
    print_colored("Launching Friday desktop UI…  (Ctrl+C to stop everything)", "33")
    print_colored("─" * get_terminal_width(), "90")
    update_event = threading.Event()
    stop_event = threading.Event()
    _start_auto_update_monitor(root, update_event, stop_event)
    procs: list[subprocess.Popen] = []
    try:
        while True:
            try:
                procs = _start_ui_processes(desktop)
                _open_ui_browser()
                break
            except RuntimeError as exc:
                _terminate_processes(procs)
                procs.clear()
                print_colored(f"\nFriday UI startup failed: {exc}", "31")
                print_colored("Retrying startup in 2 seconds…", "33")
                time.sleep(2.0)

        while True:
            time.sleep(1.0)
            if update_event.is_set():
                print_colored("\nFriday update detected — restarting safely…", "33")
                _terminate_processes(procs)
                procs.clear()
                result = subprocess.run([sys.executable, os.path.join(root, "scripts", "update.py"), "--build"], cwd=root, check=False)
                if result.returncode == 0:
                    stop_event.set()
                    os.execv(sys.executable, [sys.executable, *sys.argv])
                print_colored("Update could not be fully applied; restarting Friday on the latest source available.", "31")
                update_event.clear()
                stop_event.clear()
                _start_auto_update_monitor(root, update_event, stop_event)
                procs = _start_ui_processes(desktop)
                _open_ui_browser()
            elif any(p.poll() is not None for p in procs):
                print_colored("\nFriday UI process stopped — restarting the UI while keeping update monitoring active.", "33")
                _terminate_processes(procs)
                procs.clear()
                time.sleep(2.0)
                procs = _start_ui_processes(desktop)
                _open_ui_browser()
    except KeyboardInterrupt:
        print_colored("\nShutting down Friday UI…", "33")
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
        try:
            sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description="Friday — AI Assistant")
    parser.add_argument("--lang", choices=["english", "hinglish"], default="english", help="Language (default: english)")
    parser.add_argument("--no-confirm", action="store_true", help="Skip confirmation prompts for destructive tool calls")
    parser.add_argument("--ui", action="store_true", help="Launch the full desktop UI (API server + frontend dev server)")
    args = parser.parse_args()
    if args.ui:
        _launch_ui()
        return
    lang = args.lang
    label = LANG_LABELS.get(lang, "English")
    print_colored(BANNER, "36")
    print_colored("─" * get_terminal_width(), "90")
    print_colored(f"Friday — {label} AI Assistant (Ctrl+C to exit, /help for commands)", "33")
    print_colored("─" * get_terminal_width(), "90")
    print()
    discover_plugins()
    agent = Agent(language=lang, confirm_enabled=not args.no_confirm)
    try:
        _repl_loop(agent)
    finally:
        try:
            from browser import close_browser
        except ImportError:
            close_browser = None
        if close_browser:
            close_browser()


def _repl_loop(agent: Agent):
    while True:
        try:
            text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not text:
            continue
        if text.lower() in {"exit", "quit", "/exit", "/quit"}:
            return
        if text.lower() == "/help":
            print("Commands: /help, /exit, /quit, /lang <english|hinglish>")
            continue
        if text.lower().startswith("/lang "):
            lang = text.split(None, 1)[1].strip().lower()
            if lang in LANG_LABELS:
                agent.language = lang
                print_colored(f"Language: {LANG_LABELS[lang]}", "32")
            else:
                print_colored("Unknown language.", "31")
            continue
        try:
            result = agent.run(text)
            if result:
                print_colored(result, "37")
        except Exception as exc:
            print_colored(f"Error: {exc}", "31")


if __name__ == "__main__":
    main()
