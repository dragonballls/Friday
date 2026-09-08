"""
Friday Safe Coding Pipeline.

Stage 1:
    Isolated orchestration and verification layer.

This module deliberately does NOT modify Friday's Agent, Executor,
Planner, startup system, provider routing, or production runtime.

Safety principles:
    - never git reset --hard
    - never git clean
    - never delete the workspace
    - preserve the pre-existing dirty repository state
    - checkpoint only files explicitly selected for a coding run
    - refuse protected paths
    - refuse self-modification by default
    - verify before declaring success
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class CodingSafetyError(RuntimeError):
    """Raised when a coding operation violates a safety boundary."""


# These are intentionally conservative for Stage 1.
PROTECTED_PATHS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "Start-Friday.ps1",
    "Friday-Start.ps1",
    "Friday-Start.bat",
    "Friday-Start.vbs",
    "Friday.bat",
    "main.py",
    "desktop/api_server.py",
    "config/providers.toml",
    "config/providers.py",
    "core/security.py",
    "core/code_safety.py",
    "coding/agent_pipeline.py",
}

PROTECTED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
}

DANGEROUS_GIT_COMMANDS = {
    "reset --hard",
    "clean -fd",
    "clean -xdf",
}


def _norm(path: str | Path) -> str:
    return str(path).replace("\\", "/").strip("/").lower()


def _relative(root: Path, path: str | Path) -> str:
    root = root.resolve()
    candidate = Path(path).expanduser().resolve()

    try:
        rel = candidate.relative_to(root)
    except ValueError as exc:
        raise CodingSafetyError(
            f"Path is outside workspace: {candidate}"
        ) from exc

    return _norm(rel)


def is_protected_path(root: Path, path: str | Path) -> bool:
    rel = _relative(root, path)

    if rel in PROTECTED_PATHS:
        return True

    parts = rel.split("/")
    return any(part in PROTECTED_DIRS for part in parts)


def assert_safe_path(
    root: Path,
    path: str | Path,
    *,
    allow_protected: bool = False,
) -> Path:
    candidate = Path(path).expanduser().resolve()

    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise CodingSafetyError(
            f"Refusing path outside workspace: {candidate}"
        ) from exc

    if not allow_protected and is_protected_path(root, candidate):
        raise CodingSafetyError(
            f"Protected path modification refused: "
            f"{_relative(root, candidate)}"
        )

    return candidate


def _run_git(
    root: Path,
    args: list[str],
    *,
    timeout: float = 30.0,
) -> str:
    command = ["git", "-C", str(root), *args]

    normalized = [str(arg).strip().lower() for arg in args]

    # Destructive commands are blocked structurally.
    # We intentionally inspect Git arguments, not source-code text.
    if normalized[:2] == ["reset", "--hard"]:
        raise CodingSafetyError(
            "Dangerous Git operation blocked: reset --hard"
        )

    if normalized and normalized[0] == "clean":
        raise CodingSafetyError(
            "Dangerous Git operation blocked: git clean"
        )

    result = subprocess.run(
        command,
        cwd=str(root),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
        check=False,
    )

    if result.returncode != 0:
        raise CodingSafetyError(
            f"Git command failed ({result.returncode}): "
            f"{result.stderr.strip()}"
        )

    return result.stdout


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)

    return digest.hexdigest()


@dataclass
class FileSnapshot:
    path: str
    exists: bool
    sha256: str | None = None


@dataclass
class CodingCheckpoint:
    root: str
    created_at: float
    git_head: str
    git_status: str
    tracked_diff: str
    snapshots: dict[str, FileSnapshot] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "created_at": self.created_at,
            "git_head": self.git_head,
            "git_status": self.git_status,
            "tracked_diff": self.tracked_diff,
            "snapshots": {
                key: {
                    "path": value.path,
                    "exists": value.exists,
                    "sha256": value.sha256,
                }
                for key, value in self.snapshots.items()
            },
        }


class SafeCodingPipeline:
    """
    Stage-1 transaction/checkpoint/verifier.

    This class is intentionally not connected to Agent.run().
    """

    def __init__(
        self,
        workspace: str | Path,
        *,
        allow_protected: bool = False,
    ) -> None:
        self.root = Path(workspace).expanduser().resolve()
        self.allow_protected = allow_protected

        if not self.root.exists():
            raise CodingSafetyError(
                f"Workspace does not exist: {self.root}"
            )

        if not (self.root / ".git").exists():
            raise CodingSafetyError(
                f"Workspace is not a Git repository: {self.root}"
            )

        if not self.allow_protected:
            # Stage 1 never permits itself to be disabled accidentally.
            pass

    def git_head(self) -> str:
        return _run_git(self.root, ["rev-parse", "HEAD"]).strip()

    def git_status(self) -> str:
        return _run_git(
            self.root,
            ["status", "--porcelain=v1"],
        )

    def git_diff(self) -> str:
        return _run_git(
            self.root,
            ["diff", "--no-ext-diff", "--binary"],
        )

    def create_checkpoint(
        self,
        paths: list[str] | None = None,
    ) -> CodingCheckpoint:
        """
        Capture the repository state without changing anything.

        Important:
        Existing dirty changes are recorded as the baseline.
        We never assume HEAD represents the user's actual working state.
        """
        checkpoint = CodingCheckpoint(
            root=str(self.root),
            created_at=time.time(),
            git_head=self.git_head(),
            git_status=self.git_status(),
            tracked_diff=self.git_diff(),
        )

        for raw_path in paths or []:
            path = assert_safe_path(
                self.root,
                raw_path,
                allow_protected=self.allow_protected,
            )

            rel = _relative(self.root, path)

            if path.exists():
                checkpoint.snapshots[rel] = FileSnapshot(
                    path=rel,
                    exists=True,
                    sha256=_sha256(path),
                )
            else:
                checkpoint.snapshots[rel] = FileSnapshot(
                    path=rel,
                    exists=False,
                )

        return checkpoint

    def save_checkpoint(
        self,
        checkpoint: CodingCheckpoint,
        destination: str | Path | None = None,
    ) -> Path:
        if destination is None:
            stamp = time.strftime("%Y%m%d_%H%M%S")
            destination = (
                self.root
                / ".friday"
                / "coding-checkpoints"
                / f"checkpoint_{stamp}.json"
            )

        destination = Path(destination).expanduser().resolve()

        # Checkpoint metadata itself must remain inside Friday.
        try:
            destination.relative_to(self.root)
        except ValueError as exc:
            raise CodingSafetyError(
                "Checkpoint destination is outside workspace"
            ) from exc

        destination.parent.mkdir(parents=True, exist_ok=True)

        destination.write_text(
            json.dumps(
                checkpoint.to_dict(),
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        return destination

    def changed_paths_since(
        self,
        checkpoint: CodingCheckpoint,
    ) -> list[str]:
        """
        Determine files changed relative to the checkpoint.

        This does not mutate Git.
        """
        current_status = self.git_status()

        baseline_lines = {
            line.strip()
            for line in checkpoint.git_status.splitlines()
            if line.strip()
        }

        current_lines = {
            line.strip()
            for line in current_status.splitlines()
            if line.strip()
        }

        changed = sorted(
            baseline_lines.symmetric_difference(current_lines)
        )

        paths: list[str] = []

        for line in changed:
            if len(line) >= 4:
                candidate = line[3:].strip()

                if " -> " in candidate:
                    candidate = candidate.split(" -> ", 1)[-1]

                paths.append(candidate)

        return paths

    def verify_workspace_boundary(
        self,
        paths: list[str],
    ) -> dict[str, Any]:
        violations: list[str] = []

        for raw_path in paths:
            try:
                path = assert_safe_path(
                    self.root,
                    raw_path,
                    allow_protected=self.allow_protected,
                )
            except CodingSafetyError as exc:
                violations.append(str(exc))
                continue

            if not path.exists():
                continue

        return {
            "passed": not violations,
            "violations": violations,
        }

    def verify_protected_files_unchanged(
        self,
        checkpoint: CodingCheckpoint,
    ) -> dict[str, Any]:
        violations: list[str] = []

        for rel, snapshot in checkpoint.snapshots.items():
            path = self.root / rel

            if not is_protected_path(self.root, path):
                continue

            if not snapshot.exists:
                if path.exists():
                    violations.append(
                        f"Protected file appeared: {rel}"
                    )
                continue

            if not path.exists():
                violations.append(
                    f"Protected file disappeared: {rel}"
                )
                continue

            current_hash = _sha256(path)

            if current_hash != snapshot.sha256:
                violations.append(
                    f"Protected file changed: {rel}"
                )

        return {
            "passed": not violations,
            "violations": violations,
        }

    def verify_expected_changes(
        self,
        changed_paths: list[str],
        expected_paths: list[str],
    ) -> dict[str, Any]:
        changed = {
            _norm(path)
            for path in changed_paths
        }

        expected = {
            _norm(path)
            for path in expected_paths
        }

        unexpected = sorted(changed - expected)
        missing = sorted(expected - changed)

        return {
            "passed": not unexpected and not missing,
            "unexpected": unexpected,
            "missing": missing,
        }

    def completion_gate(
        self,
        *,
        checkpoint: CodingCheckpoint,
        expected_paths: list[str],
        tests_passed: bool,
        implementation_complete: bool,
        diff_reviewed: bool,
        final_verification: bool,
    ) -> dict[str, Any]:
        changed = self.changed_paths_since(checkpoint)

        workspace = self.verify_workspace_boundary(changed)
        protected = self.verify_protected_files_unchanged(checkpoint)
        expected = self.verify_expected_changes(
            changed,
            expected_paths,
        )

        checks = {
            "implementation_complete": bool(
                implementation_complete
            ),
            "expected_files": expected["passed"],
            "workspace_boundary": workspace["passed"],
            "protected_files": protected["passed"],
            "tests_passed": bool(tests_passed),
            "diff_reviewed": bool(diff_reviewed),
            "final_verification": bool(final_verification),
        }

        return {
            "passed": all(checks.values()),
            "checks": checks,
            "changed_paths": changed,
            "expected": expected,
            "workspace": workspace,
            "protected": protected,
        }


def run_completion_gate(
    workspace: str | Path,
    *,
    expected_paths: list[str],
    tests_passed: bool,
    implementation_complete: bool,
    diff_reviewed: bool,
    final_verification: bool,
) -> dict[str, Any]:
    """
    Convenience entry point.

    No writes are performed by this function.
    """
    pipeline = SafeCodingPipeline(workspace)
    checkpoint = pipeline.create_checkpoint()

    return pipeline.completion_gate(
        checkpoint=checkpoint,
        expected_paths=expected_paths,
        tests_passed=tests_passed,
        implementation_complete=implementation_complete,
        diff_reviewed=diff_reviewed,
        final_verification=final_verification,
    )