#!/usr/bin/env python3
"""Start Friday after safely applying available source updates.

The desktop UI already has a background update monitor, so its launcher should
not block startup on a network Git fetch. The normal CLI path still performs
the safe startup update check.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UPDATER = ROOT / "scripts" / "update.py"
MAIN = ROOT / "main.py"


def main() -> int:
    args = sys.argv[1:]

    # The UI supervisor checks origin/main in the background once it is running.
    # Avoid making the user wait on Git/network availability before the UI can
    # even start. This also prevents a slow/offline Git remote from looking like
    # a broken Friday launch.
    if "--ui" not in args:
        result = subprocess.run([sys.executable, str(UPDATER)], cwd=ROOT, check=False)
        if result.returncode not in (0, 2, 3, 4):
            print(f"Friday update failed (code {result.returncode}); launching current checkout.", file=sys.stderr)

    return subprocess.run([sys.executable, str(MAIN), *args], cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
