from __future__ import annotations

import asyncio
import os
import socket
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import webview
from hypercorn.asyncio import serve
from hypercorn.config import Config


def resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]


ROOT = resource_root()
DIST = ROOT / "desktop" / "dist"
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


def install_startup() -> None:
    if os.name != "nt" or "--smoke-test" in sys.argv:
        return
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
