from __future__ import annotations

import asyncio
import multiprocessing
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import zipfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen, Request

API_HOST = "127.0.0.1"
API_PORT = 8080
UI_HOST = "127.0.0.1"
UI_PORT = 5173
SMOKE_WATCHDOG_SECONDS = 35.0
REPO_ZIP_URL = "https://github.com/dragonballls/Friday/archive/refs/heads/main.zip"
WORKSPACE_NAME = "Friday-SelfCoding-Workspace"


def resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]


ROOT = resource_root()
DIST = ROOT / "desktop" / "dist"


def log_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "friday.log"
    return Path.cwd() / "friday.log"


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
    os._exit(code)


def self_coding_workspace() -> Path:
    return Path.home() / WORKSPACE_NAME


def prepare_self_coding_workspace() -> Path:
    workspace = self_coding_workspace()
    if (workspace / ".git").is_dir() and (workspace / "agent").is_dir():
        return workspace

    workspace.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix="friday-bootstrap-"))
    archive_path = temp_dir / "friday-main.zip"
    extracted = temp_dir / "extracted"
    try:
        log(f"Preparing self-coding workspace: {workspace}")
        request = Request(REPO_ZIP_URL, headers={"User-Agent": "Jarvis/1.0"})
        with urlopen(request, timeout=60) as response:
            archive_path.write_bytes(response.read())
        with zipfile.ZipFile(archive_path) as archive:
            bad = [
                name for name in archive.namelist()
                if Path(name).is_absolute() or Path(name).drive or ".." in Path(name).parts
            ]
            if bad:
                raise RuntimeError("GitHub source archive contained an unsafe path")
            archive.extractall(extracted)
        roots = [p for p in extracted.iterdir() if p.is_dir()]
        if len(roots) != 1:
            raise RuntimeError("Unexpected GitHub source archive layout")
        source = roots[0]
        if workspace.exists():
            shutil.rmtree(workspace, ignore_errors=True)
        shutil.copytree(source, workspace)
        log("Self-coding workspace ready")
        return workspace
    except Exception:
        shutil.rmtree(workspace, ignore_errors=True)
        log("Self-coding workspace preparation failed:\n" + traceback.format_exc())
        raise
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def wait_for_port(host: str, port: int, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(f"Jarvis service did not become ready on {host}:{port}")


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *_args) -> None:
        return


def start_static_server(port: int = UI_PORT) -> ThreadingHTTPServer:
    if not DIST.is_dir() or not (DIST / "index.html").is_file():
        raise RuntimeError(f"Frontend bundle missing: {DIST / 'index.html'}")

    def handler(*args, **kwargs):
        return QuietHandler(*args, directory=str(DIST), **kwargs)

    server = ThreadingHTTPServer((UI_HOST, port), handler)
    thread = threading.Thread(target=server.serve_forever, name="jarvis-static", daemon=True)
    thread.start()
    return server


async def _api_server() -> None:
    sys.path.insert(0, str(ROOT))
    log("API process importing desktop.api_server")
    from desktop.api_server import app
    config = Config()
    config.bind = [f"{API_HOST}:{API_PORT}"]
    config.accesslog = None
    config.errorlog = None
    config.loglevel = "warning"
    await serve(app, config)


def run_api_process() -> None:
    try:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(_api_server())
    except Exception:
        log("API process crashed:\n" + traceback.format_exc())
        raise


def start_api_server_process() -> subprocess.Popen:
    exe = Path(sys.executable).resolve()
    command = [str(exe), "--api-server"] if getattr(sys, "frozen", False) else [sys.executable, str(Path(__file__).resolve()), "--api-server"]
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    log("starting dedicated API process")
    return subprocess.Popen(
        command,
        cwd=str(ROOT),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )


def http_text(url: str) -> tuple[int, str] | None:
    try:
        with urlopen(url, timeout=3) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except (OSError, URLError):
        return None


async def quart_health_check() -> tuple[int, str]:
    sys.path.insert(0, str(ROOT))
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
        raise RuntimeError(f"Jarvis frontend bundle is missing: {DIST}")
    os.environ["JARVIS_SMOKE_TEST"] = "1"
    ui_server = start_static_server(port=0)
    smoke_port = int(ui_server.server_address[1])
    log(f"smoke-test UI listening on {UI_HOST}:{smoke_port}")
    try:
        wait_for_port(UI_HOST, smoke_port)
        ui = http_text(f"http://{UI_HOST}:{smoke_port}/")
        if ui is None or ui[0] != 200:
            raise RuntimeError("Jarvis UI did not return HTTP 200 on the root page")
        html = ui[1]
        if "<title>Jarvis</title>" not in html:
            raise RuntimeError("Jarvis UI root page did not contain the expected title")
        if "/Friday/assets/" in html:
            raise RuntimeError("Windows UI bundle incorrectly references /Friday/ assets")
        if "/assets/" not in html:
            raise RuntimeError("Jarvis UI root page did not contain a production asset reference")
        log("smoke-test UI checks passed")
        status, body = asyncio.run(quart_health_check())
        if status != 200:
            raise RuntimeError(f"Jarvis API health endpoint returned HTTP {status}: {body}")
        log("smoke-test API health passed")
    finally:
        ui_server.shutdown()
        ui_server.server_close()


def install_startup() -> None:
    if os.name != "nt" or "--smoke-test" in sys.argv or "--api-server" in sys.argv:
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
            winreg.SetValueEx(key, "Jarvis", 0, winreg.REG_SZ, f'"{exe}" --startup')
    except OSError:
        pass


def main() -> None:
    if "--smoke-test" in sys.argv:
        arm_smoke_watchdog()
        log("smoke-test starting")
        smoke_test()
        log("smoke-test completed")
        hard_exit(0)

    if "--api-server" in sys.argv:
        run_api_process()
        return

    if not DIST.exists():
        raise SystemExit(f"Jarvis frontend bundle is missing: {DIST}")

    workspace = prepare_self_coding_workspace()
    os.environ["JARVIS_WORKSPACE"] = str(workspace)

    import webview
    install_startup()
    start_static_server()
    api_process = start_api_server_process()
    try:
        wait_for_port(API_HOST, API_PORT, timeout=30.0)
        wait_for_port(UI_HOST, UI_PORT, timeout=10.0)
        webview.create_window(
            "Jarvis",
            f"http://{UI_HOST}:{UI_PORT}/",
            width=1440,
            height=900,
            min_size=(1050, 700),
            resizable=True,
            text_select=True,
        )
        webview.start(debug=False)
    finally:
        if api_process.poll() is None:
            api_process.terminate()
            try:
                api_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                api_process.kill()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    try:
        main()
    except Exception:
        log(traceback.format_exc())
        if "--smoke-test" in sys.argv:
            hard_exit(1)
        raise
