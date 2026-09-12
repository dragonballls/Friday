from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "build" / "windows" / "Friday"
EXE = BUNDLE / "Friday.exe"
UPDATER = BUNDLE / "FridayUpdater.exe"
VERSION = BUNDLE / "VERSION"
LOG = BUNDLE / "smoke_test.log"
TIMEOUT_SECONDS = 45


def dump_log() -> None:
    if not LOG.is_file():
        print(f"No packaged smoke-test log was written at {LOG}", flush=True)
        return
    print("----- Friday.exe smoke_test.log -----", flush=True)
    print(LOG.read_text(encoding="utf-8", errors="replace"), end="", flush=True)
    print("----- end smoke_test.log -----", flush=True)


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
    for required in (EXE, UPDATER, VERSION):
        if not required.is_file():
            raise SystemExit(f"Missing Windows bundle file: {required}")
    version = VERSION.read_text(encoding="utf-8").strip()
    if not version:
        raise SystemExit("Windows bundle VERSION file is empty")
    if LOG.exists():
        LOG.unlink()

    proc = subprocess.Popen(
        [str(EXE), "--smoke-test"],
        cwd=str(EXE.parent),
        stdin=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            returncode = proc.poll()
            if returncode is not None:
                dump_log()
                if returncode != 0:
                    raise SystemExit(f"Friday.exe smoke test exited with code {returncode}")
                print(f"Friday Windows bundle smoke test passed for version {version}.", flush=True)
                return
            time.sleep(0.25)
        dump_log()
        raise SystemExit(f"Friday.exe smoke test did not complete within {TIMEOUT_SECONDS} seconds")
    finally:
        terminate(proc)


if __name__ == "__main__":
    main()
