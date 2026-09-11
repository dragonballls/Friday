from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import webview
from hypercorn.asyncio import serve
from hypercorn.config import Config


GITHUB_REPO = "dragonballls/Friday"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}"


def resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]


ROOT = resource_root()
EXE_DIR = Path(sys.executable).resolve().parent
DIST = ROOT / "desktop" / "dist"
UPDATER = EXE_DIR / "FridayUpdater.exe"
VERSION_FILE = EXE_DIR / "VERSION"
API_HOST = "127.0.0.1"
API_PORT = 8080
UI_HOST = "127.0.0.1"
UI_PORT = 5173


def wait_for_port(host: str, port: int, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(f"Friday service did not become ready on {host}:{port}")


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *_args) -> None:
        return


def start_static_server() -> ThreadingHTTPServer:
    if not DIST.is_dir() or not (DIST / "index.html").is_file():
        raise RuntimeError(f"Frontend bundle missing: {DIST / 'index.html'}")
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(DIST), **kwargs)
    server = ThreadingHTTPServer((UI_HOST, UI_PORT), handler)
    thread = threading.Thread(target=server.serve_forever, name="friday-static", daemon=True)
    thread.start()
    return server


def start_api_server() -> threading.Thread:
    sys.path.insert(0, str(ROOT))
    from desktop.api_server import app

    config = Config()
    config.bind = [f"{API_HOST}:{API_PORT}"]
    config.accesslog = None
    config.errorlog = None
    config.loglevel = "warning"

    def runner() -> None:
        asyncio.run(serve(app, config))

    thread = threading.Thread(target=runner, name="friday-api", daemon=True)
    thread.start()
    return thread


def _http_json(url: str) -> dict:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {"api.github.com", "github.com"}:
        raise ValueError("unexpected GitHub URL")
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "Friday-Windows-Updater",
        },
        method="GET",
    )
    with urlopen(request, timeout=10) as response:
        return json.load(response)


def _current_build_commit() -> str:
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return "dev"


def _latest_windows_artifact() -> tuple[str, str] | None:
    runs_url = f"{GITHUB_API}/actions/workflows/windows-app.yml/runs?branch=main&status=success&per_page=5"
    runs = _http_json(runs_url).get("workflow_runs", [])
    for run in runs:
        if run.get("head_branch") != "main" or run.get("conclusion") != "success":
            continue
        head_sha = str(run.get("head_sha") or "").strip()
        run_id = run.get("id")
        if not head_sha or not run_id:
            continue
        artifacts = _http_json(f"{GITHUB_API}/actions/runs/{run_id}/artifacts?name=Friday-Windows&per_page=5").get("artifacts", [])
        for artifact in artifacts:
            if artifact.get("name") == "Friday-Windows" and not artifact.get("expired"):
                archive_url = str(artifact.get("archive_download_url") or "").strip()
                parsed = urlparse(archive_url)
                if parsed.scheme == "https" and parsed.hostname == "api.github.com":
                    return head_sha, archive_url
    return None


def _download_artifact(url: str) -> str:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "Friday-Windows-Updater",
        },
        method="GET",
    )
    fd, path = tempfile.mkstemp(prefix="friday-update-", suffix=".zip")
    os.close(fd)
    try:
        with urlopen(request, timeout=60) as response, open(path, "wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
        return path
    except Exception:
        try:
            os.remove(path)
        except OSError:
            pass
        raise


def maybe_update_native_bundle() -> bool:
    """Download the newest successful Windows main-branch artifact and hand off replacement."""
    if not getattr(sys, "frozen", False) or "--smoke-test" in sys.argv or not UPDATER.is_file():
        return False
    try:
        latest = _latest_windows_artifact()
        if latest is None:
            return False
        latest_sha, archive_url = latest
        if latest_sha == _current_build_commit():
            return False
        archive = _download_artifact(archive_url)
        subprocess.Popen(
            [
                str(UPDATER),
                "--pid",
                str(os.getpid()),
                "--target",
                str(EXE_DIR),
                "--archive",
                archive,
                "--exe",
                str(EXE_DIR / "Friday.exe"),
            ],
            cwd=EXE_DIR,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0x00000008) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200),
        )
        return True
    except (OSError, ValueError, TypeError, KeyError, TimeoutError, json.JSONDecodeError):
        return False


def _remove_legacy_startup_task() -> None:
    if os.name != "nt":
        return
    try:
        subprocess.run(
            ["schtasks", "/Delete", "/TN", "Friday UI", "/F"],
            capture_output=True,
            text=True,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def install_startup() -> None:
    if os.name != "nt" or "--smoke-test" in sys.argv:
        return
    _remove_legacy_startup_task()
    try:
        import winreg

        exe = Path(sys.executable).resolve()
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, "Friday", 0, winreg.REG_SZ, f'"{exe}" --startup')
    except OSError:
        pass


def main() -> None:
    if not DIST.exists():
        raise SystemExit(f"Friday frontend bundle is missing: {DIST}")

    if maybe_update_native_bundle():
        raise SystemExit(0)

    install_startup()
    start_static_server()
    start_api_server()
    wait_for_port(API_HOST, API_PORT)
    wait_for_port(UI_HOST, UI_PORT)

    webview.create_window(
        "Friday",
        f"http://{UI_HOST}:{UI_PORT}/",
        width=1440,
        height=900,
        min_size=(1050, 700),
        resizable=True,
        text_select=True,
    )
    webview.start(debug=False)


if __name__ == "__main__":
    main()
