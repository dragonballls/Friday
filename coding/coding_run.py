from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from coding.durable_transaction import (
    DurableCodingTransaction,
    DurableTransactionError,
)
from coding.safe_transaction import (
    _norm,
    _relative,
    assert_safe_path,
)


class CodingRunError(DurableTransactionError):
    """Raised when a safe coding run cannot complete safely."""


@dataclass(frozen=True)
class WorkspaceFileState:
    relative_path: str
    is_file: bool
    sha256: str | None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inventory_workspace(workspace: Path) -> dict[str, WorkspaceFileState]:
    """
    Read-only inventory of regular files in the workspace.

    This is used to detect mutations outside the explicitly authorized
    coding surface. It never modifies the workspace.
    """
    result: dict[str, WorkspaceFileState] = {}
    ignored_roots = {
        ".git",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        ".pytest_cache",
        "node_modules",
        "dist",
        "coverage",
        "htmlcov",
    }

    for path in workspace.rglob("*"):
        try:
            relative = _norm(_relative(workspace, path))
        except Exception:
            continue

        # Never inspect transaction metadata or generated/runtime trees
        # as part of the coding surface. Verification tools legitimately
        # create caches and build output while checking a source change.
        parts = Path(relative).parts

        if parts and parts[0] in ignored_roots:
            continue

        if path.is_file():
            result[relative] = WorkspaceFileState(
                relative_path=relative,
                is_file=True,
                sha256=_sha256(path),
            )

    return result


class SafeCodingRun:
    """
    Safety adapter for a single Friday coding operation.

    Responsibilities:

    1. Define the exact authorized coding surface.
    2. Persist pre-run snapshots outside the workspace.
    3. Preserve pre-existing dirty files exactly.
    4. Reject protected paths.
    5. Detect modifications outside the authorized surface.
    6. Roll back authorized changes after a failed run.
    7. Leave successful authorized changes in place.
    8. Never use destructive Git commands.
    """

    def __init__(
        self,
        workspace: str | Path,
        expected_paths: Iterable[str | Path],
        transaction_id: str | None = None,
    ):
        self.workspace = Path(workspace).resolve()

        if not self.workspace.exists():
            raise CodingRunError(
                f"Workspace does not exist: {self.workspace}"
            )

        normalized: list[str] = []
        seen: set[str] = set()

        for raw_path in expected_paths:
            target = assert_safe_path(
                self.workspace,
                raw_path,
            )

            relative = _norm(
                _relative(
                    self.workspace,
                    target,
                )
            )

            if relative not in seen:
                seen.add(relative)
                normalized.append(relative)

        if not normalized:
            raise CodingRunError(
                "Safe coding run requires at least one expected path."
            )

        self.expected_paths = frozenset(normalized)

        self.transaction = DurableCodingTransaction(
            self.workspace,
            transaction_id=transaction_id,
        )

        self._baseline: dict[str, WorkspaceFileState] = {}
        self._started = False
        self._completed = False
        self._failed = False

    @property
    def started(self) -> bool:
        return self._started

    @property
    def completed(self) -> bool:
        return self._completed

    @property
    def failed(self) -> bool:
        return self._failed

    @property
    def transaction_id(self) -> str:
        return self.transaction.transaction_id

    def start(self) -> None:
        if self._started:
            raise CodingRunError(
                "Coding run has already started."
            )

        self._baseline = _inventory_workspace(
            self.workspace
        )

        # Snapshot only the explicitly authorized coding surface.
        self.transaction.begin(
            sorted(self.expected_paths)
        )

        self._started = True

    def authorize(self, path: str | Path) -> Path:
        """
        Authorize an expected path.

        Dynamic authorization is deliberately restricted to the
        expected-path set established before the run.
        """
        if not self._started:
            raise CodingRunError(
                "Coding run has not started."
            )

        target = assert_safe_path(
            self.workspace,
            path,
        )

        relative = _norm(
            _relative(
                self.workspace,
                target,
            )
        )

        if relative not in self.expected_paths:
            raise CodingRunError(
                "Path is outside the declared coding surface: "
                f"{relative}"
            )

        self.transaction.authorize(relative)

        return target

    def changed_paths(self) -> set[str]:
        if not self._started:
            raise CodingRunError(
                "Coding run has not started."
            )

        current = _inventory_workspace(
            self.workspace
        )

        all_paths = set(self._baseline) | set(current)
        changed: set[str] = set()

        for relative in all_paths:
            before = self._baseline.get(relative)
            after = current.get(relative)

            if before != after:
                changed.add(relative)

        return changed

    def unexpected_changes(self) -> set[str]:
        changed = self.changed_paths()

        return {
            path
            for path in changed
            if path not in self.expected_paths
        }

    def verify_surface(self) -> None:
        unexpected = self.unexpected_changes()

        if unexpected:
            raise CodingRunError(
                "Coding run modified paths outside the authorized "
                "coding surface: "
                + ", ".join(sorted(unexpected))
            )

    def finish(
        self,
        implementation_complete: bool = True,
        test_passed: bool = True,
        review_passed: bool = True,
        final_verification_passed: bool = True,
    ) -> dict[str, object]:
        if not self._started:
            raise CodingRunError(
                "Coding run has not started."
            )

        if self._completed:
            raise CodingRunError(
                "Coding run has already completed."
            )

        if not implementation_complete:
            raise CodingRunError(
                "Completion gate failed: implementation incomplete."
            )

        if not test_passed:
            raise CodingRunError(
                "Completion gate failed: tests did not pass."
            )

        if not review_passed:
            raise CodingRunError(
                "Completion gate failed: review did not pass."
            )

        if not final_verification_passed:
            raise CodingRunError(
                "Completion gate failed: final verification did not pass."
            )

        self.verify_surface()

        changed = self.changed_paths()

        self._completed = True
        self._failed = False

        return {
            "success": True,
            "transaction_id": self.transaction_id,
            "changed_paths": sorted(changed),
            "expected_paths": sorted(self.expected_paths),
        }

    def fail_and_rollback(self) -> dict[str, str]:
        if not self._started:
            raise CodingRunError(
                "Coding run has not started."
            )

        if self._completed:
            raise CodingRunError(
                "Cannot roll back a completed coding run."
            )

        # Roll back only the explicitly authorized paths.
        result = self.transaction.rollback()

        self._failed = True
        self._completed = False

        return result

    def run(
        self,
        task: Callable[["SafeCodingRun"], object],
        *,
        test_fn: Callable[[], bool] | None = None,
        review_fn: Callable[[], bool] | None = None,
        final_verification_fn: Callable[[], bool] | None = None,
    ) -> dict[str, object]:
        """
        Execute a coding task inside the durable safety boundary.

        Any exception causes authorized files to be rolled back.
        Unexpected workspace mutations are detected before success
        is declared.
        """
        self.start()

        try:
            task(self)

            test_passed = (
                True
                if test_fn is None
                else bool(test_fn())
            )

            review_passed = (
                True
                if review_fn is None
                else bool(review_fn())
            )

            final_verification_passed = (
                True
                if final_verification_fn is None
                else bool(final_verification_fn())
            )

            return self.finish(
                implementation_complete=True,
                test_passed=test_passed,
                review_passed=review_passed,
                final_verification_passed=final_verification_passed,
            )

        except Exception:
            self.fail_and_rollback()
            raise


def create_safe_coding_run(
    workspace: str | Path,
    expected_paths: Iterable[str | Path],
    transaction_id: str | None = None,
) -> SafeCodingRun:
    return SafeCodingRun(
        workspace,
        expected_paths,
        transaction_id=transaction_id,
    )
