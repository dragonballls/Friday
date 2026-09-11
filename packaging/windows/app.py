from __future__ import annotations

import asyncio
import hashlib
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

    def handler(*args, **kwargs):
        return QuietHandler(*args, directory=str(DIST), **kwargs)

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
