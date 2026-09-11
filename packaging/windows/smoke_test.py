from __future__ import annotations

import socket
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "build" / "windows" / "Friday"
EXE = BUNDLE / "Friday.exe"
UPDATER = BUNDLE / "FridayUpdater.exe"
VERSION = BUNDLE / "VERSION"


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def http_text(url: str) -> tuple[int, str] | None:
    try:
        with urlopen(url, timeout=2) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except (OSError, URLError):
        return None


def main() -> None:
    for required in (EXE, UPDATER, VERSION):
        if not required.is_file():
            raise SystemExit(f"Missing Windows bundle file: {required}")
    version = VERSION.read_text(encoding="utf-8").strip()
    if not version:
        raise SystemExit("Windows bundle VERSION file is empty")

    proc = subprocess.Popen([str(EXE), "--smoke-test"], cwd=EXE.parent)
    try:
        deadline = time.monotonic() + 30
        api_ready = False
        ui_ready = False
        while time.monotonic() < deadline:
            api_ready = api_ready or port_open(8080)
            ui_ready = ui_ready or port_open(5173)
            if api_ready and ui_ready:
                break
            if proc.poll() is not None:
                raise SystemExit(f"Friday.exe exited early with code {proc.returncode}")
            time.sleep(0.25)
        else:
            raise SystemExit("Friday.exe did not expose both 8080 and 5173 within 30 seconds")

        ui = http_text("http://127.0.0.1:5173/")
        if ui is None or ui[0] != 200:
            raise SystemExit("Friday UI did not return HTTP 200 on the root page")
        html = ui[1]
        if "<title>Friday</title>" not in html:
            raise SystemExit("Friday UI root page did not contain the expected title")
        if "/Friday/assets/" in html:
            raise SystemExit("Windows UI bundle incorrectly references the GitHub Pages /Friday/ asset base path")
        if "/assets/" not in html:
            raise SystemExit("Friday UI root page did not contain a production asset reference")

        health = http_text("http://127.0.0.1:8080/api/v1/health")
        if health is None or health[0] != 200:
            raise SystemExit("Friday API health endpoint did not return HTTP 200")

        print("Friday Windows bundle smoke test passed: UI HTML/assets and API health are live.")
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
