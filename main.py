import argparse
import os
import shutil
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
 |_|   |_|\__,_|\__, |_|\___|
                |___/
"""
LANG_LABELS = {"english": "English", "hinglish": "Hinglish"}
AUTO_UPDATE_INTERVAL = 60
DEFAULT_UI_PORT = 5173


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


def _start_ui_processes(desktop: str, port: int) -> list[subprocess.Popen]:
    api_cmd = [sys.executable, os.path.join(desktop, "api_server.py")]
    front_cmd = ["npm", "run", "dev", "--", "--port", str(port)]
    if sys.platform == "win32":
        front_cmd = ["cmd", "/c", "npm", "run", "dev", "--", "--port", str(port)]
    child_env = os.environ.copy()
    child_env["FRIDAY_UI_PORT"] = str(port)
    child_env["FRONTEND_ORIGIN"] = f"http://localhost:{port}"
    procs: list[subprocess.Popen] = []
    api = subprocess.Popen(api_cmd, cwd=desktop, env=child_env)
    procs.append(api)
    time.sleep(2.0)
    front = subprocess.Popen(front_cmd, cwd=desktop, env=child_env, creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0)
    procs.append(front)
    return procs


def _launch_ui(port: int = DEFAULT_UI_PORT):
    """Launch the UI and keep its source/runtime synchronized with origin/main."""
    root = os.path.dirname(os.path.abspath(__file__))
    desktop = os.path.join(root, "desktop")
    print_colored(BANNER, "36")
    print_colored("─" * get_terminal_width(), "90")
    print_colored(f"Launching Friday desktop UI on port {port}…  (Ctrl+C to stop everything)", "33")
    print_colored("─" * get_terminal_width(), "90")
    update_event = threading.Event()
    stop_event = threading.Event()
    _start_auto_update_monitor(root, update_event, stop_event)
    procs: list[subprocess.Popen] = []
    try:
        procs = _start_ui_processes(desktop, port)
        time.sleep(5.0)
        webbrowser.open(f"http://localhost:{port}")
        while True:
            time.sleep(1.0)
            if update_event.is_set():
                print_colored("\nFriday update detected — restarting safely…", "33")
                _terminate_processes(procs)
                procs.clear()
                result = subprocess.run([sys.executable, os.path.join(root, "scripts", "update.py")], cwd=root, check=False)
                if result.returncode == 0:
                    stop_event.set()
                    os.execv(sys.executable, [sys.executable, *sys.argv])
                print_colored("Update could not be applied; keeping Friday available on the current version.", "31")
                update_event.clear()
                _start_auto_update_monitor(root, update_event, stop_event)
                procs = _start_ui_processes(desktop, port)
            elif any(p.poll() is not None for p in procs):
                print_colored("\nFriday UI process stopped — restarting the UI while keeping update monitoring active.", "33")
                _terminate_processes(procs)
                procs.clear()
                time.sleep(2.0)
                procs = _start_ui_processes(desktop, port)
                webbrowser.open(f"http://localhost:{port}")
    except KeyboardInterrupt:
        print_colored("\nShutting down Friday UI…", "33")
    finally:
        stop_event.set()
        _terminate_processes(procs)


def main():
    parser = argparse.ArgumentParser(description="Friday — AI Assistant")
    parser.add_argument("--lang", choices=["english", "hinglish"], default="english", help="Language (default: english)")
    parser.add_argument("--no-confirm", action="store_true", help="Skip confirmation prompts for destructive tool calls")
    parser.add_argument("--ui", action="store_true", help="Launch the full desktop UI (API server + frontend dev server)")
    parser.add_argument("--port", type=int, default=DEFAULT_UI_PORT, help=f"Frontend UI port when using --ui (default: {DEFAULT_UI_PORT})")
    args = parser.parse_args()
    if args.port < 1024 or args.port > 65535:
        parser.error("--port must be between 1024 and 65535")
    if args.ui:
        _launch_ui(args.port)
        return
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
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
            return
        close_browser()


def _repl_loop(agent: Agent):
    while True:
        try:
            user_input = input("\033[32m❯\033[0m ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            print_colored("Bye bye! 👋", "33")
            sys.exit(0)
        if not user_input:
            continue
        if user_input.startswith("/"):
            handled = _handle_command(user_input, agent)
            if handled == "exit":
                break
            continue
        print()
        for event in agent.run(user_input):
            if event["type"] == "tokens":
                print(event["content"], end="", flush=True)
            elif event["type"] == "requires_confirmation":
                print_colored(f"  ⚠ Tool '{event['tool']}' requires confirmation:", "33")
                print_colored(f"     Args: {event.get('args') or '{}'}", "90")
                while True:
                    try:
                        answer = input("\033[33m  Allow? [y/N]\033[0m ").strip().lower()
                    except (EOFError, KeyboardInterrupt):
                        answer = "n"
                    if answer in ("y", "yes"):
                        agent.resolve_approval(event["request_id"], True)
                        break
                    if answer in ("n", "no", ""):
                        agent.resolve_approval(event["request_id"], False)
                        break
            elif event["type"] == "tool_result":
                for t in event.get("tools", []):
                    print_colored(f"  🛠 {t['name']}({t['args']})", "90")
                    print_colored(f"     Result: {t['result']}", "90")
        print("\n")


def _voice_loop(agent: Agent):
    if not is_voice_available():
        print_colored("Voice not available — no microphone detected. Install pyaudio for voice support.", "31")
        return
    print_colored("Voice mode active. Speak now. Say 'exit' or press Ctrl+C to return to text mode.", "33")
    print_colored("Listening...", "33")
    while True:
        try:
            result = listen()
        except KeyboardInterrupt:
            return
        except Exception as exc:
            print_colored(f"Voice error: {exc}", "31")
            continue
        if not result:
            continue
        print_colored(f"You: {result}", "32")
        if result.lower().strip() == "exit":
            return
        for event in agent.run(result):
            if event["type"] == "tokens":
                speak(event["content"])


def _handle_command(command: str, agent: Agent):
    cmd = command.lower().split()[0]
    if cmd == "/help":
        _print_help()
    elif cmd == "/exit":
        return "exit"
    elif cmd == "/voice":
        _voice_loop(agent)
    else:
        print_colored(f"Unknown command: {command}. Type /help for available commands.", "31")
    return None


def _print_help():
    print_colored("Available commands:", "36")
    print("  /help   Show this help")
    print("  /voice  Enter voice mode")
    print("  /exit   Exit Friday")
