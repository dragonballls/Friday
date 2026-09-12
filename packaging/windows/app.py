from __future__ import annotations

import asyncio
import os
import socket
import sys
import threading
import time
import traceback
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

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


def http_text(url: str) -> tuple[int, str] | None:
    try:
        with urlopen(url, timeout=3) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except (OSError, URLError):
        return None


def smoke_test() -> None:
    """Validate the frozen bundle without starting the full desktop server stack.

    The normal application still starts Hypercorn and the static server. Smoke
    mode intentionally exercises the packaged frontend and the Quart health
    endpoint through Quart's in-process test client. This avoids CI hangs caused
    by background server/event-loop lifetime while still testing the packaged
    API route and the exact frontend assets shipped in the executable.
    """
    if not DIST.exists():
        raise RuntimeError(f"Friday frontend bundle is missing: {DIST}")

    static_server = start_static_server()
    try:
        wait_for_port(UI_HOST, UI_PORT)

        ui = http_text(f"http://{UI_HOST}:{UI_PORT}/")
        if ui is None or ui[0] != 200:
            raise RuntimeError("Friday UI did not return HTTP 200 on the root page")
        html = ui[1]
        if "<title>Friday</title>" not in html:
            raise RuntimeError("Friday UI root page did not contain the expected title")
        if "/Friday/assets/" in html:
            raise RuntimeError("Windows UI bundle incorrectly references the GitHub Pages /Friday/ asset base path")
        if "/assets/" not in html:
            raise RuntimeError("Friday UI root page did not contain a production asset reference")

        sys.path.insert(0, str(ROOT))
        from desktop.api_server import app

        async def check_api() -> None:
            client = app.test_client()
            response = await client.get(f"{API_PREFIX}/health")
            if response.status_code != 200:
                raise RuntimeError(
                    f"Friday API health endpoint returned HTTP {response.status_code}"
                )

        asyncio.run(check_api())
        print("Friday Windows bundle smoke test passed: packaged UI assets and API health are valid.")
    finally:
        static_server.shutdown()
        static_server.server_close()


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
    if "--smoke-test" in sys.argv:
        smoke_test()
        print("Friday Windows bundle smoke test completed.", flush=True)
        os._exit(0)

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
    try:
        main()
    except Exception:
        log_path = Path(sys.executable).resolve().parent / "smoke_test.log"
        try:
            log_path.write_text(traceback.format_exc(), encoding="utf-8")
        except OSError:
            pass
        raise
