from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "build" / "windows" / "Friday-Barebones"
EXE = BUNDLE / "Friday-Barebones.exe"
VERSION = BUNDLE / "VERSION"
TIMEOUT_SECONDS = 45


def dump_log() -> None:
    log = BUNDLE / "friday.log"
    if log.is_file():
        print("----- packaged Friday log -----", flush=True)
        print(log.read_text(encoding="utf-8", errors="replace"), end="", flush=True)
        print("----- end packaged Friday log -----", flush=True)


def terminate(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            capture_output=True,
            check=False,
        )
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def main() -> None:
    for required in (EXE, VERSION):
        if not required.is_file():
            raise SystemExit(f"Missing Windows bundle file: {required}")
    version = VERSION.read_text(encoding="utf-8").strip()
    if not version:
        raise SystemExit("Windows bundle VERSION file is empty")

    proc = subprocess.Popen(
        [str(EXE), "--smoke-test"],
        cwd=str(EXE.parent),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0,
    )
    try:
        deadline = time.monotonic() + TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            returncode = proc.poll()
            if returncode is not None:
                dump_log()
                if returncode != 0:
                    raise SystemExit(f"Friday-Barebones.exe smoke test exited with code {returncode}")
                print(f"Friday barebones Windows bundle smoke test passed for version {version}.", flush=True)
                return
            time.sleep(0.25)
        dump_log()
        raise SystemExit(f"Friday-Barebones.exe smoke test did not complete within {TIMEOUT_SECONDS} seconds")
    finally:
        terminate(proc)


if __name__ == "__main__":
    main()
