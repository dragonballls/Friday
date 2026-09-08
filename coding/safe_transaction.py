from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


class CodingTransactionError(RuntimeError):
    """Raised when a coding transaction violates its safety rules."""


PROTECTED_PATHS = {
    "start-friday.ps1",
    "friday-start.ps1",
    "friday-start.bat",
    "friday-start.vbs",
    "friday.bat",
    "main.py",
    "desktop/api_server.py",
    "config/providers.toml",
    "config/providers.py",
    "core/security.py",
    "core/code_safety.py",
    "coding/safe_transaction.py",
    "coding/agent_pipeline.py",
}

PROTECTED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
}


def _norm(path: str | Path) -> str:
    return str(path).replace("\\", "/").strip("/")


def _relative(root: Path, path: str | Path) -> Path:
    root = root.resolve()
    target = Path(path).resolve()

    try:
        return target.relative_to(root)
    except ValueError as exc:
        raise CodingTransactionError(
            f"Path escapes Friday workspace: {path}"
        ) from exc


def is_protected_path(root: Path, path: str | Path) -> bool:
    rel = _relative(root, path)
    normalized = _norm(rel).lower()

    if normalized in PROTECTED_PATHS:
        return True

    parts = normalized.split("/")
    return any(part in PROTECTED_DIRS for part in parts)


def assert_safe_path(
    root: Path,
    path: str | Path,
    *,
    allow_protected: bool = False,
) -> Path:
    root = root.resolve()
    target = Path(path)

    if not target.is_absolute():
        target = root / target

    target = target.resolve()

    # Workspace confinement is always enforced.
    rel = _relative(root, target)

    if not allow_protected and is_protected_path(root, target):
        raise CodingTransactionError(
            f"Protected path blocked: {rel}"
        )

    return target


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class FileSnapshot:
    relative_path: str
    existed: bool
    is_file: bool
    content: bytes | None
    sha256: str | None

    @classmethod
    def capture(cls, root: Path, path: Path) -> "FileSnapshot":
        rel = _relative(root, path)
        normalized = _norm(rel)

        if not path.exists():
            return cls(
                relative_path=normalized,
                existed=False,
                is_file=False,
                content=None,
                sha256=None,
            )

        if not path.is_file():
            raise CodingTransactionError(
                f"Only regular files may be transaction targets: {rel}"
            )

        content = path.read_bytes()

        return cls(
            relative_path=normalized,
            existed=True,
            is_file=True,
            content=content,
            sha256=_sha256_bytes(content),
        )


class SafeCodingTransaction:
    """
    Exact filesystem transaction for one Friday coding run.

    The transaction snapshots only explicitly authorized paths.

    If a path already contains user modifications before the run,
    those exact bytes become the rollback state.

    If a path does not exist before the run, rollback removes only
    the file created by this run.

    No Git reset/clean/restore operations are performed.
    """

    def __init__(self, workspace: str | Path):
        self.workspace = Path(workspace).resolve()

        if not self.workspace.exists():
            raise CodingTransactionError(
                f"Workspace does not exist: {self.workspace}"
            )

        self._snapshots: dict[str, FileSnapshot] = {}
        self._active = False
        self._rolled_back = False

    @property
    def active(self) -> bool:
        return self._active

    @property
    def rolled_back(self) -> bool:
        return self._rolled_back

    @property
    def snapshots(self) -> dict[str, FileSnapshot]:
        return dict(self._snapshots)

    def begin(self, paths: Iterable[str | Path]) -> None:
        if self._active:
            raise CodingTransactionError(
                "Transaction is already active."
            )

        targets = list(paths)

        if not targets:
            raise CodingTransactionError(
                "Transaction requires at least one authorized path."
            )

        for raw_path in targets:
            target = assert_safe_path(self.workspace, raw_path)

            rel = _norm(_relative(self.workspace, target))

            if rel in self._snapshots:
                continue

            self._snapshots[rel] = FileSnapshot.capture(
                self.workspace,
                target,
            )

        self._active = True
        self._rolled_back = False

    def authorize(self, path: str | Path) -> Path:
        if not self._active:
            raise CodingTransactionError(
                "Transaction has not been started."
            )

        target = assert_safe_path(self.workspace, path)

        rel = _norm(_relative(self.workspace, target))

        if rel not in self._snapshots:
            self._snapshots[rel] = FileSnapshot.capture(
                self.workspace,
                target,
            )

        return target

    def _snapshot_for(self, path: Path) -> FileSnapshot:
        rel = _norm(_relative(self.workspace, path))

        snapshot = self._snapshots.get(rel)

        if snapshot is None:
            raise CodingTransactionError(
                f"Path was not authorized before modification: {rel}"
            )

        return snapshot

    def rollback(self) -> dict[str, str]:
        if not self._active:
            raise CodingTransactionError(
                "Cannot rollback an inactive transaction."
            )

        restored: dict[str, str] = {}

        for snapshot in self._snapshots.values():
            target = self.workspace / snapshot.relative_path

            # Re-check workspace and protection before every restoration.
            target = assert_safe_path(
                self.workspace,
                target,
                allow_protected=True,
            )

            if snapshot.existed:
                if snapshot.content is None:
                    raise CodingTransactionError(
                        f"Snapshot content missing: {snapshot.relative_path}"
                    )

                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(snapshot.content)

                restored[snapshot.relative_path] = "restored"
            else:
                # Only remove a file that this transaction created.
                # Never recursively delete directories.
                if target.exists():
                    if target.is_file():
                        target.unlink()
                        restored[snapshot.relative_path] = "removed_created_file"
                    else:
                        raise CodingTransactionError(
                            "Rollback refused to delete a directory: "
                            f"{snapshot.relative_path}"
                        )
                else:
                    restored[snapshot.relative_path] = "already_absent"

        self._rolled_back = True
        self._active = False

        return restored

    def verify_snapshot_state(self) -> dict[str, bool]:
        """
        Verify that all authorized paths exactly match their
        pre-run state.
        """

        results: dict[str, bool] = {}

        for snapshot in self._snapshots.values():
            target = self.workspace / snapshot.relative_path

            if not snapshot.existed:
                results[snapshot.relative_path] = not target.exists()
                continue

            if not target.is_file():
                results[snapshot.relative_path] = False
                continue

            content = target.read_bytes()
            results[snapshot.relative_path] = (
                _sha256_bytes(content) == snapshot.sha256
                and content == snapshot.content
            )

        return results

    def changed_from_snapshot(self) -> list[str]:
        changed: list[str] = []

        for snapshot in self._snapshots.values():
            target = self.workspace / snapshot.relative_path

            if not snapshot.existed:
                if target.exists():
                    changed.append(snapshot.relative_path)
                continue

            if not target.is_file():
                changed.append(snapshot.relative_path)
                continue

            current = target.read_bytes()

            if current != snapshot.content:
                changed.append(snapshot.relative_path)

        return sorted(changed)


def create_safe_transaction(
    workspace: str | Path,
    paths: Iterable[str | Path],
) -> SafeCodingTransaction:
    transaction = SafeCodingTransaction(workspace)
    transaction.begin(paths)
    return transaction