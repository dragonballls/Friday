from __future__ import annotations

import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "build" / "windows" / "Friday"
EXE = BUNDLE / "Friday.exe"
UPDATER = BUNDLE / "FridayUpdater.exe"
VERSION = BUNDLE / "VERSION"


def main() -> None:
    for required in (EXE, UPDATER, VERSION):
        if not required.is_file():
            raise SystemExit(f"Missing Windows bundle file: {required}")
    version = VERSION.read_text(encoding="utf-8").strip()
    if not version:
        raise SystemExit("Windows bundle VERSION file is empty")

    proc = subprocess.Popen([str(EXE), "--smoke-test"], cwd=EXE.parent)
    try:
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            returncode = proc.poll()
            if returncode is not None:
                if returncode != 0:
                    raise SystemExit(f"Friday.exe smoke test exited with code {returncode}")
                print(f"Friday Windows bundle smoke test passed for version {version}.")
                return
            time.sleep(0.25)
        raise SystemExit("Friday.exe smoke test did not complete within 40 seconds")
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
