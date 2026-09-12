from __future__ import annotations

import asyncio
import multiprocessing
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

from hypercorn.asyncio import serve
from hypercorn.config import Config

API_HOST = "127.0.0.1"
API_PORT = 8080
UI_HOST = "127.0.0.1"
UI_PORT = 5173
SMOKE_WATCHDOG_SECONDS = 35.0


def resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]


ROOT = resource_root()
DIST = ROOT / "desktop" / "dist"


def log_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "smoke_test.log"
    return Path.cwd() / "smoke_test.log"


def log(message: str) -> None:
    line = message.rstrip() + "\n"
    try:
        with log_path().open("a", encoding="utf-8") as handle:
            handle.write(line)
    except OSError:
        pass
    try:
        if sys.stdout is not None:
            print(message, flush=True)
    except OSError:
        pass


def hard_exit(code: int) -> None:
    # Windowed PyInstaller bootloaders show a blocking error dialog on uncaught
    # exceptions. Force-exit so CI never waits on a click that will never come.
    os._exit(code)


def wait_for_port(host: str, port: int, timeout: float = 20.0) -> None:
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
    log("importing desktop.api_server")
    from desktop.api_server import app

    config = Config()
    config.bind = [f"{API_HOST}:{API_PORT}"]
    config.accesslog = None
    config.errorlog = None
    config.loglevel = "warning"

    def runner() -> None:
        try:
            if sys.platform == "win32":
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            asyncio.run(serve(app, config))
        except Exception:
            log("API server thread crashed:\n" + traceback.format_exc())

    thread = threading.Thread(target=runner, name="friday-api", daemon=True)
    thread.start()
    return thread


def http_text(url: str) -> tuple[int, str] | None:
    try:
        with urlopen(url, timeout=3) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except (OSError, URLError):
        return None


async def quart_health_check() -> tuple[int, str]:
    sys.path.insert(0, str(ROOT))
    log("importing desktop.api_server for in-process health check")
    from desktop.api_server import app

    client = app.test_client()
    response = await client.get("/api/v1/health")
    body = await response.get_data(as_text=True)
    return response.status_code, body


def arm_smoke_watchdog(seconds: float = SMOKE_WATCHDOG_SECONDS) -> None:
    def expire() -> None:
        log(f"smoke-test watchdog expired after {seconds:.0f} seconds")
        hard_exit(2)

    timer = threading.Timer(seconds, expire)
    timer.daemon = True
    timer.start()


def smoke_test() -> None:
    if not DIST.exists():
        raise RuntimeError(f"Friday frontend bundle is missing: {DIST}")

    os.environ["FRIDAY_SMOKE_TEST"] = "1"
    log(f"serving UI from {DIST}")
    ui_server = start_static_server()
    try:
        log("checking UI port")
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

        # Do not launch Hypercorn in a background thread on Windows: Hypercorn
        # installs signal handlers and Python only permits that in the main thread.
        # The packaged smoke test only needs to verify that the bundled Quart app
        # imports and that its health route responds, so use Quart's in-process
        # test client instead of binding port 8080.
        log("checking API health in-process")
        status, body = asyncio.run(quart_health_check())
        if status != 200:
            raise RuntimeError(f"Friday API health endpoint returned HTTP {status}: {body}")

        log("Friday Windows bundle smoke test passed: UI HTML/assets and API health are valid.")
    finally:
        ui_server.shutdown()
        ui_server.server_close()


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
        arm_smoke_watchdog()
        log("smoke-test starting")
        smoke_test()
        log("smoke-test completed")
        hard_exit(0)

    if not DIST.exists():
        raise SystemExit(f"Friday frontend bundle is missing: {DIST}")

    import webview

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
    multiprocessing.freeze_support()
    try:
        main()
    except Exception:
        log(traceback.format_exc())
        if "--smoke-test" in sys.argv:
            hard_exit(1)
        raise
