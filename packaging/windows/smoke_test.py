from __future__ import annotations

import socket
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXE = ROOT / "build" / "windows" / "Friday" / "Friday.exe"


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def main() -> None:
    if not EXE.is_file():
        raise SystemExit(f"Missing executable: {EXE}")

    proc = subprocess.Popen([str(EXE), "--smoke-test"], cwd=EXE.parent)
    try:
        deadline = time.monotonic() + 30
        api_ready = False
        ui_ready = False
        while time.monotonic() < deadline:
            api_ready = api_ready or port_open(8080)
            ui_ready = ui_ready or port_open(5173)
            if api_ready and ui_ready:
                print("Friday Windows bundle smoke test passed: API and UI ports are live.")
                return
            if proc.poll() is not None:
                raise SystemExit(f"Friday.exe exited early with code {proc.returncode}")
            time.sleep(0.25)
        raise SystemExit("Friday.exe did not expose both 8080 and 5173 within 30 seconds")
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
