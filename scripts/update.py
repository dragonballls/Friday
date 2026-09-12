#!/usr/bin/env python3
"""Safely update a Jarvis source checkout from its configured Git remote.

The updater never resets, force-checks out, or overwrites local changes. It
migrates legacy Friday origins to the canonical Jarvis repository, then applies
fast-forward updates only. Build failures roll back to the previous commit.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "desktop"
CANONICAL_REMOTE_URL = "https://github.com/dragonballls/Jarvis.git"


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


def _ensure_jarvis_remote(remote: str) -> int:
    """Migrate legacy Friday installations to the canonical Jarvis repository."""
    result = subprocess.run(
        ["git", "remote", "get-url", remote],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Unable to read git remote '{remote}'.", file=sys.stderr)
        return 1
    current_url = result.stdout.strip()
    normalized = current_url.rstrip("/").lower()
    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    if normalized.endswith("/dragonballls/jarvis"):
        return 0
    if "friday" in normalized:
        print(f"Migrating legacy Friday remote '{current_url}' to Jarvis.")
        return run(["git", "remote", "set-url", remote, CANONICAL_REMOTE_URL])
    print(f"Git remote '{remote}' is not the canonical Jarvis repository: {current_url}", file=sys.stderr)
    return 2


def _npm_command() -> str | None:
    if sys.platform == "win32":
        return shutil.which("npm.cmd") or shutil.which("npm")
    return shutil.which("npm")


def _clear_frontend_port() -> None:
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
        if parts[3].upper() == "LISTENING" and local_address.rsplit(":", 1)[-1] == "5173" and parts[4].isdigit():
            pids.add(parts[4])
    for pid in pids:
        subprocess.run(["taskkill", "/PID", pid, "/T", "/F"], cwd=ROOT, check=False, capture_output=True, text=True)


def _frontend_dependencies_ready() -> bool:
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
    if not working_tree_is_clean():
        print("Rollback refused because the working tree is no longer clean.", file=sys.stderr)
        return False
    if run(["git", "reset", "--hard", commit]) != 0:
        print(f"CRITICAL: unable to roll back Jarvis to known-good commit {commit}.", file=sys.stderr)
        return False
    print(f"Rolled Jarvis back to known-good commit {commit}.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely update Jarvis from GitHub")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()

    if shutil.which("git") is None:
        print("git is required", file=sys.stderr)
        return 1

    migration_result = _ensure_jarvis_remote(args.remote)
    if migration_result == 1:
        return 3
    if migration_result == 2:
        return 4

    branch = current_branch()
    if branch != args.branch:
        if not working_tree_is_clean():
            print(f"Refusing to switch from '{branch or 'detached HEAD'}' to '{args.branch}' because local changes exist.", file=sys.stderr)
            return 2
        print(f"Local checkout is on '{branch or 'detached HEAD'}'; safely switching to '{args.branch}'.")
        if run(["git", "fetch", "--prune", args.remote, args.branch]) != 0:
            return 3
        if run(["git", "checkout", args.branch]) != 0:
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
            return 7 if rollback_to(old_commit) else 9
        if not DESKTOP.is_dir():
            return 6 if rollback_to(old_commit) else 9
        if _install_frontend_dependencies(npm) != 0 or not _frontend_dependencies_ready():
            print("Frontend dependency installation failed or remained incomplete; rolling back the update.", file=sys.stderr)
            return 7 if rollback_to(old_commit) else 9
        if run([npm, "run", "build"], cwd=DESKTOP) != 0:
            print("Frontend build failed; rolling back the update.", file=sys.stderr)
            return 8 if rollback_to(old_commit) else 9

    print("Jarvis is up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
