#!/usr/bin/env python3
"""Safely update a Friday source checkout from its configured Git remote.

The updater never resets, force-checks out, or overwrites local changes. When a
clean checkout is on another branch, it safely switches to the requested branch
so the desktop launcher cannot remain stuck on an old feature branch. The
original branch and its commits remain intact.

When ``--build`` is requested, the previous commit is retained as a rollback
point. If dependency installation or the frontend build fails after the
fast-forward, Friday automatically returns to the known-good commit instead of
leaving the running installation on a potentially broken update.
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


def working_tree_is_clean() -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr.strip() or "Unable to inspect git status.", file=sys.stderr)
        return False
    if result.stdout.strip():
        print("Refusing to update: working tree has local changes.", file=sys.stderr)
        print(result.stdout.strip(), file=sys.stderr)
        return False
    return True


def current_branch() -> str | None:
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def current_commit() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _npm_command() -> str | None:
    """Return an executable npm command that works with Windows .cmd shims."""
    if sys.platform == "win32":
        return shutil.which("npm.cmd") or shutil.which("npm")
    return shutil.which("npm")


def _clear_frontend_port() -> None:
    """Kill only the Windows process tree currently owning Vite's port."""
    if sys.platform != "win32":
        return

    try:
        result = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return

    if result.returncode != 0:
        return

    pids: set[str] = set()
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0].upper() != "TCP":
            continue
        local_address = parts[1]
        state = parts[3].upper()
        pid = parts[4]
        if state != "LISTENING":
            continue
        if local_address.rsplit(":", 1)[-1] == "5173" and pid.isdigit():
            pids.add(pid)

    for pid in pids:
        subprocess.run(
            ["taskkill", "/PID", pid, "/T", "/F"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )


def _frontend_dependencies_ready() -> bool:
    """Confirm npm installed the build tools required by the frontend scripts."""
    node_modules = DESKTOP / "node_modules"
    vite_package = node_modules / "vite" / "package.json"
    typescript_package = node_modules / "typescript" / "package.json"
    if sys.platform == "win32":
        vite_bin = node_modules / ".bin" / "vite.cmd"
        tsc_bin = node_modules / ".bin" / "tsc.cmd"
    else:
        vite_bin = node_modules / ".bin" / "vite"
        tsc_bin = node_modules / ".bin" / "tsc"
    return all(path.is_file() for path in (vite_package, typescript_package, vite_bin, tsc_bin))


def _install_frontend_dependencies(npm: str) -> int:
    """Install dependencies and recover once from a partial npm tree."""
    _clear_frontend_port()
    result = run([npm, "ci"], cwd=DESKTOP)
    if result != 0:
        return result
    if _frontend_dependencies_ready():
        return 0

    print("npm ci completed but the frontend dependency tree is incomplete; retrying from a clean node_modules.", file=sys.stderr)
    _clear_frontend_port()
    node_modules = DESKTOP / "node_modules"
    if node_modules.exists():
        shutil.rmtree(node_modules, ignore_errors=False)
    return run([npm, "ci"], cwd=DESKTOP)


def rollback_to(commit: str) -> bool:
    """Return to a known-good commit without touching user changes."""
    if not working_tree_is_clean():
        print("Rollback refused because the working tree is no longer clean.", file=sys.stderr)
        return False
    if run(["git", "reset", "--hard", commit]) != 0:
        print(f"CRITICAL: unable to roll back Friday to known-good commit {commit}.", file=sys.stderr)
        return False
    print(f"Rolled Friday back to known-good commit {commit}.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely update Friday from GitHub")
    parser.add_argument("--remote", default="origin", help="Git remote (default: origin)")
    parser.add_argument("--branch", default="main", help="Remote branch (default: main)")
    parser.add_argument("--build", action="store_true", help="Install frontend dependencies and build after updating")
    args = parser.parse_args()

    if shutil.which("git") is None:
        print("git is required", file=sys.stderr)
        return 1

    branch = current_branch()
    if branch != args.branch:
        if not working_tree_is_clean():
            print(
                f"Refusing to switch from '{branch or 'detached HEAD'}' to '{args.branch}' because local changes exist.",
                file=sys.stderr,
            )
            return 2
        print(
            f"Local checkout is on '{branch or 'detached HEAD'}'; safely switching to '{args.branch}'. "
            "The original branch and its commits are preserved."
        )
        if run(["git", "fetch", "--prune", args.remote, args.branch]) != 0:
            return 3
        if run(["git", "checkout", args.branch]) != 0:
            print("Unable to switch to the requested branch; leaving the checkout unchanged.", file=sys.stderr)
            return 4

    if not working_tree_is_clean():
        return 2
    if run(["git", "fetch", "--prune", args.remote, args.branch]) != 0:
        return 3

    old_commit = current_commit()
    if old_commit is None:
        print("Unable to determine the current commit; refusing to update.", file=sys.stderr)
        return 4

    remote_ref = f"{args.remote}/{args.branch}"
    if run(["git", "merge", "--ff-only", remote_ref]) != 0:
        print("Update is not a fast-forward; no local history was rewritten.", file=sys.stderr)
        return 4

    if args.build:
        npm = _npm_command()
        if npm is None:
            print("npm is required for --build; rolling back the update.", file=sys.stderr)
            return 7 if rollback_to(old_commit) else 9
        if not DESKTOP.is_dir():
            print(f"Desktop directory not found: {DESKTOP}; rolling back the update.", file=sys.stderr)
            return 6 if rollback_to(old_commit) else 9
        if _install_frontend_dependencies(npm) != 0 or not _frontend_dependencies_ready():
            print("Frontend dependency installation failed or remained incomplete; rolling back the update.", file=sys.stderr)
            return 7 if rollback_to(old_commit) else 9
        if run([npm, "run", "build"], cwd=DESKTOP) != 0:
            print("Frontend build failed; rolling back the update.", file=sys.stderr)
            return 8 if rollback_to(old_commit) else 9

    print("Friday is up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
