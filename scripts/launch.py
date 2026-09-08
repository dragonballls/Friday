#!/usr/bin/env python3
"""Start Friday after safely applying available source updates.

This is the normal source-checkout launcher. It never overwrites local work:
if the checkout is dirty, the updater refuses the update and Friday starts at
the current revision. A network/update failure is also non-fatal so an already
working checkout can still launch.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UPDATER = ROOT / "scripts" / "update.py"
MAIN = ROOT / "main.py"


def main() -> int:
    result = subprocess.run([sys.executable, str(UPDATER)], cwd=ROOT, check=False)
    if result.returncode not in (0, 2, 3, 4):
        print(f"Friday update failed (code {result.returncode}); launching current checkout.", file=sys.stderr)

    return subprocess.run([sys.executable, str(MAIN), *sys.argv[1:]], cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
