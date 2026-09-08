#!/usr/bin/env python3
"""Safely update a Friday source checkout from its configured Git remote.

The updater never resets, force-checks out, or overwrites local changes. It only
performs a fast-forward pull when the working tree is clean, then optionally
installs frontend dependencies and builds the desktop bundle.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "desktop"


def run(command: list[str], *, cwd: Path = ROOT) -> int:
    print("$", " ".join(command))
    return subprocess.run(command, cwd=cwd, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely update Friday from GitHub")
    parser.add_argument("--remote", default="origin", help="Git remote (default: origin)")
    parser.add_argument("--branch", default="main", help="Remote branch (default: main)")
    parser.add_argument("--build", action="store_true", help="Install frontend dependencies and build after updating")
    args = parser.parse_args()

    if shutil.which("git") is None:
        print("git is required", file=sys.stderr)
        return 1

    if run(["git", "diff", "--quiet"]) != 0 or run(["git", "diff", "--cached", "--quiet"]) != 0:
        print("Refusing to update: working tree has local changes.", file=sys.stderr)
        return 2

    if run(["git", "fetch", "--prune", args.remote, args.branch]) != 0:
        return 3

    remote_ref = f"{args.remote}/{args.branch}"
    if run(["git", "merge", "--ff-only", remote_ref]) != 0:
        print("Update is not a fast-forward; no local history was rewritten.", file=sys.stderr)
        return 4

    if args.build:
        if shutil.which("npm") is None:
            print("npm is required for --build", file=sys.stderr)
            return 5
        if run(["npm", "ci"], cwd=DESKTOP) != 0:
            return 6
        if run(["npm", "run", "build"], cwd=DESKTOP) != 0:
            return 7

    print("Friday is up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
