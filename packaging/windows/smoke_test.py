from __future__ import annotations

import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build" / "windows"
EXE = BUILD / "Jarvis.exe"
SMOKE_BUNDLE = BUILD / "_smoke" / "JarvisSmoke"
SMOKE_EXE = SMOKE_BUNDLE / "JarvisSmoke.exe"
VERSION = BUILD / "VERSION"
LOG = BUILD / "jarvis.log"


def dump_log() -> None:
    if not LOG.is_file():
        print("No packaged Jarvis log was produced.")
        return
    try:
        print("----- packaged jarvis.log -----")
        print(LOG.read_text(encoding="utf-8", errors="replace"))
        print("----- end packaged jarvis.log -----")
    except OSError as exc:
        print(f"Could not read packaged Jarvis log: {exc}")


def main() -> None:
    for required in (EXE, SMOKE_EXE, VERSION):
        if not required.is_file():
            raise SystemExit(f"Missing Windows Jarvis file: {required}")
    version = VERSION.read_text(encoding="utf-8").strip()
    if not version:
        raise SystemExit("Windows Jarvis VERSION file is empty")

    # The smoke binary uses a console bootloader so native boot/import failures
    # are visible in CI while the real user app remains GUI-only.
    proc = subprocess.Popen([str(SMOKE_EXE), "--smoke-test"], cwd=SMOKE_BUNDLE)
    try:
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            returncode = proc.poll()
            if returncode is not None:
                if returncode != 0:
                    dump_log()
                    raise SystemExit(f"JarvisSmoke.exe smoke test exited with code {returncode}")
                print(f"Jarvis single-file Windows app smoke test passed for version {version}.")
                dump_log()
                return
            time.sleep(0.25)
        dump_log()
        raise SystemExit("JarvisSmoke.exe smoke test did not complete within 40 seconds")
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
