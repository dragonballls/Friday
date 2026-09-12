#!/usr/bin/env python3
"""Safely update a Friday source checkout from its configured Git remote.

The updater never resets, force-checks out, or overwrites local changes. A
candidate update is validated in an isolated Git worktree before the live
checkout is changed. This is important for the background updater: a clean
checkout must not be treated as proof that a new commit is safe to run.

The isolated validation runs the frontend dependency install, TypeScript/Vite
build, frontend tests, and a Python syntax check. Only when those checks pass,
and the live checkout is still unchanged and clean, is the candidate fast-
forwarded onto the live branch.

This means an update can fail validation without changing the running coding
checkout at all. ``--build`` is retained for compatibility with existing
launch commands; validation is now always performed before an update is
activated.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
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


def remote_commit(remote: str, branch: str) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", f"{remote}/{branch}"],
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


def _cleanup_worktree(path: Path) -> None:
    """Remove an isolated validation worktree without touching ROOT."""
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(path)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "worktree", "prune"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def _validate_candidate(commit: str) -> bool:
    """Build and test a candidate in an isolated worktree."""
    npm = _npm_command()
    if npm is None:
        print("npm is required to validate a Friday update; candidate rejected.", file=sys.stderr)
        return False
    if not DESKTOP.is_dir():
        print(f"Desktop directory not found: {DESKTOP}; candidate rejected.", file=sys.stderr)
        return False

    temp_path = Path(tempfile.mkdtemp(prefix="friday-update-", dir=tempfile.gettempdir()))
    worktree_added = False
    try:
        print(f"Validating candidate {commit[:12]} in isolated worktree {temp_path}.")
        add = subprocess.run(
            ["git", "worktree", "add", "--detach", str(temp_path), commit],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if add.returncode != 0:
            print(add.stderr.strip() or "Unable to create isolated validation worktree.", file=sys.stderr)
            return False
        worktree_added = True

        staged_desktop = temp_path / "desktop"
        if run([npm, "ci"], cwd=staged_desktop) != 0:
            print("Candidate rejected: npm ci failed in the isolated worktree.", file=sys.stderr)
            return False

        if run([npm, "run", "build"], cwd=staged_desktop) != 0:
            print("Candidate rejected: frontend build failed in the isolated worktree.", file=sys.stderr)
            return False

        if run([npm, "run", "test", "--", "--runInBand"], cwd=staged_desktop) != 0:
            print("Candidate rejected: frontend tests failed in the isolated worktree.", file=sys.stderr)
            return False

        if run([sys.executable, "-m", "compileall", "-q", "desktop", "scripts"], cwd=temp_path) != 0:
            print("Candidate rejected: Python syntax validation failed in the isolated worktree.", file=sys.stderr)
            return False

        print("Candidate validation passed.")
        return True
    finally:
        if worktree_added:
            _cleanup_worktree(temp_path)
        elif temp_path.exists():
            shutil.rmtree(temp_path, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely update Friday from GitHub")
    parser.add_argument("--remote", default="origin", help="Git remote (default: origin)")
    parser.add_argument("--branch", default="main", help="Remote branch (default: main)")
    parser.add_argument(
        "--build",
        action="store_true",
        help="Compatibility flag; candidate validation is always performed before activation",
    )
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
    remote_ref = f"{args.remote}/{args.branch}"
    candidate_commit = remote_commit(args.remote, args.branch)
    if old_commit is None or candidate_commit is None:
        print("Unable to determine current or remote commit; refusing to update.", file=sys.stderr)
        return 4

    if old_commit == candidate_commit:
        print("Friday is up to date.")
        return 0

    print(f"Update candidate detected: {old_commit[:12]} -> {candidate_commit[:12]}.")

    if not _validate_candidate(candidate_commit):
        print("Friday update left unapplied; the current checkout was not changed.", file=sys.stderr)
        return 7

    # A coding agent or user may have committed something while validation was
    # running. Never fast-forward a stale snapshot over a newly changed main.
    if not working_tree_is_clean():
        print("Live checkout changed during validation; refusing to activate candidate.", file=sys.stderr)
        return 2
    current_after_validation = current_commit()
    if current_after_validation != old_commit:
        print(
            "Live checkout moved during validation; refusing to activate the stale candidate.",
            file=sys.stderr,
        )
        return 4

    if run(["git", "merge", "--ff-only", remote_ref]) != 0:
        print("Update is no longer a fast-forward; no local history was rewritten.", file=sys.stderr)
        return 4

    print("Validated Friday update activated safely.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
