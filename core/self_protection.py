"""Safety gates for Friday's self-modification workflow.

The gate is intentionally conservative: self-modification must happen on a
non-main branch, from a known repository root, and only becomes promotable after
an external validation callback reports success. A failed validation can invoke
a supplied rollback callback, keeping mutation and promotion separate.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable


class SelfModificationBlocked(RuntimeError):
    """Raised when a self-modification violates a safety invariant."""


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    checks: tuple[str, ...]
    reason: str = ""


class SelfProtectionGate:
    """Fail-closed gate for autonomous code changes."""

    def __init__(self, repository_root: str | Path, protected_branches: tuple[str, ...] = ("main", "master")):
        self.repository_root = Path(repository_root).resolve()
        self.protected_branches = frozenset(protected_branches)

    def authorize_change(self, branch: str, target_paths: list[str] | tuple[str, ...]) -> tuple[Path, ...]:
        if not branch or branch in self.protected_branches:
            raise SelfModificationBlocked("Self-modification is blocked on a protected branch.")
        resolved: list[Path] = []
        for raw_path in target_paths:
            path = (self.repository_root / raw_path).resolve()
            try:
                path.relative_to(self.repository_root)
            except ValueError as exc:
                raise SelfModificationBlocked(f"Target escapes repository root: {raw_path}") from exc
            resolved.append(path)
        if not resolved:
            raise SelfModificationBlocked("Self-modification requires at least one explicit target path.")
        return tuple(resolved)

    def validate_and_promote(
        self,
        branch: str,
        target_paths: list[str] | tuple[str, ...],
        validator: Callable[[], ValidationResult],
        rollback: Callable[[], None],
    ) -> ValidationResult:
        self.authorize_change(branch, target_paths)
        try:
            result = validator()
        except Exception:
            rollback()
            raise
        if not result.passed:
            rollback()
            return result
        return result
