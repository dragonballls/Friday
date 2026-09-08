from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from coding.safe_transaction import (
    CodingTransactionError,
    _norm,
    _relative,
    assert_safe_path,
)


class DurableTransactionError(CodingTransactionError):
    """Raised when a durable coding transaction cannot be completed safely."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _transaction_root() -> Path:
    """Store transaction journals outside the Friday workspace."""
    root = Path(tempfile.gettempdir()) / "FridayCodingTransactions"
    root.mkdir(parents=True, exist_ok=True)
    return root


@dataclass(frozen=True)
class DurableSnapshot:
    relative_path: str
    existed: bool
    is_file: bool
    sha256: str | None
    content_file: str | None


class DurableCodingTransaction:
    """
    Crash-resistant filesystem transaction for a Friday coding run.

    Snapshot bytes are persisted outside the Friday workspace. Rollback
    restores only explicitly authorized paths to their exact pre-run state.
    """

    FORMAT_VERSION = 1

    def __init__(
        self,
        workspace: str | Path,
        transaction_id: str | None = None,
    ):
        self.workspace = Path(workspace).resolve()
        if not self.workspace.exists():
            raise DurableTransactionError(
                f"Workspace does not exist: {self.workspace}"
            )

        if transaction_id is None:
            transaction_id = uuid.uuid4().hex

        if (
            not transaction_id
            or "/" in transaction_id
            or "\\" in transaction_id
            or ".." in transaction_id
        ):
            raise DurableTransactionError("Invalid transaction ID.")

        self.transaction_id = transaction_id
        self.storage_root = _transaction_root() / self.transaction_id
        self.files_root = self.storage_root / "files"
        self.manifest_path = self.storage_root / "manifest.json"
        self._active = False
        self._rolled_back = False

    @property
    def active(self) -> bool:
        return self._active

    @property
    def rolled_back(self) -> bool:
        return self._rolled_back

    def _write_manifest(self, snapshots: list[DurableSnapshot]) -> None:
        self.storage_root.mkdir(parents=True, exist_ok=True)
        manifest = {
            "format_version": self.FORMAT_VERSION,
            "transaction_id": self.transaction_id,
            "workspace": str(self.workspace),
            "snapshots": [
                {
                    "relative_path": snapshot.relative_path,
                    "existed": snapshot.existed,
                    "is_file": snapshot.is_file,
                    "sha256": snapshot.sha256,
                    "content_file": snapshot.content_file,
                }
                for snapshot in snapshots
            ],
        }
        temp_manifest = self.storage_root / "manifest.tmp"
        temp_manifest.write_text(
            json.dumps(manifest, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(temp_manifest, self.manifest_path)

    def _load_manifest(self) -> dict:
        if not self.manifest_path.is_file():
            raise DurableTransactionError(
                f"Transaction manifest is missing: {self.manifest_path}"
            )
        try:
            manifest = json.loads(
                self.manifest_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise DurableTransactionError(
                f"Unable to read transaction manifest: {self.manifest_path}"
            ) from exc

        if not isinstance(manifest, dict):
            raise DurableTransactionError("Invalid transaction manifest.")
        if manifest.get("format_version") != self.FORMAT_VERSION:
            raise DurableTransactionError("Unsupported transaction manifest version.")
        if manifest.get("transaction_id") != self.transaction_id:
            raise DurableTransactionError("Transaction ID mismatch.")

        recorded_workspace = Path(manifest.get("workspace", "")).resolve()
        if recorded_workspace != self.workspace:
            raise DurableTransactionError("Transaction workspace mismatch.")

        snapshots = manifest.get("snapshots")
        if not isinstance(snapshots, list):
            raise DurableTransactionError("Invalid transaction snapshot manifest.")

        return manifest

    def begin(self, paths: Iterable[str | Path]) -> None:
        if self._active:
            raise DurableTransactionError("Transaction is already active.")

        targets = list(paths)
        if not targets:
            raise DurableTransactionError(
                "Transaction requires at least one authorized path."
            )

        snapshots: list[DurableSnapshot] = []
        seen: set[str] = set()
        self.storage_root.mkdir(parents=True, exist_ok=False)
        self.files_root.mkdir(parents=True, exist_ok=True)

        try:
            for raw_path in targets:
                try:
                    target = assert_safe_path(self.workspace, raw_path)
                except CodingTransactionError as exc:
                    raise DurableTransactionError(str(exc)) from exc

                rel = _norm(_relative(self.workspace, target))
                if rel in seen:
                    continue
                seen.add(rel)

                if not target.exists():
                    snapshots.append(
                        DurableSnapshot(rel, False, False, None, None)
                    )
                    continue

                if not target.is_file():
                    raise DurableTransactionError(
                        "Only regular files may be transaction targets: "
                        f"{rel}"
                    )

                content = target.read_bytes()
                content_name = f"{len(snapshots):08d}.bin"
                content_path = self.files_root / content_name
                temp_content = self.files_root / f"{content_name}.tmp"
                temp_content.write_bytes(content)
                os.replace(temp_content, content_path)
                snapshots.append(
                    DurableSnapshot(
                        rel,
                        True,
                        True,
                        _sha256_bytes(content),
                        content_name,
                    )
                )

            self._write_manifest(snapshots)
            self._load_manifest()
            self._active = True
            self._rolled_back = False
        except Exception:
            raise

    def authorize(self, path: str | Path) -> Path:
        if not self._active:
            raise DurableTransactionError("Transaction has not been started.")

        try:
            target = assert_safe_path(self.workspace, path)
        except CodingTransactionError as exc:
            raise DurableTransactionError(str(exc)) from exc

        manifest = self._load_manifest()
        existing = {item["relative_path"] for item in manifest["snapshots"]}
        rel = _norm(_relative(self.workspace, target))
        if rel in existing:
            return target

        if target.exists() and not target.is_file():
            raise DurableTransactionError(
                f"Only regular files may be authorized: {rel}"
            )

        snapshots = [
            DurableSnapshot(
                relative_path=item["relative_path"],
                existed=bool(item["existed"]),
                is_file=bool(item["is_file"]),
                sha256=item["sha256"],
                content_file=item["content_file"],
            )
            for item in manifest["snapshots"]
        ]

        if target.exists():
            content = target.read_bytes()
            content_name = f"{len(snapshots):08d}.bin"
            content_path = self.files_root / content_name
            temp_content = self.files_root / f"{content_name}.tmp"
            temp_content.write_bytes(content)
            os.replace(temp_content, content_path)
            snapshots.append(
                DurableSnapshot(
                    rel,
                    True,
                    True,
                    _sha256_bytes(content),
                    content_name,
                )
            )
        else:
            snapshots.append(DurableSnapshot(rel, False, False, None, None))

        self._write_manifest(snapshots)
        return target

    def _snapshots(self) -> list[DurableSnapshot]:
        manifest = self._load_manifest()
        return [
            DurableSnapshot(
                relative_path=item["relative_path"],
                existed=bool(item["existed"]),
                is_file=bool(item["is_file"]),
                sha256=item["sha256"],
                content_file=item["content_file"],
            )
            for item in manifest["snapshots"]
        ]

    def rollback(self) -> dict[str, str]:
        if not self._active:
            raise DurableTransactionError("Cannot rollback an inactive transaction.")

        restored: dict[str, str] = {}
        snapshots = self._snapshots()

        for snapshot in snapshots:
            target = self.workspace / snapshot.relative_path
            target = assert_safe_path(
                self.workspace,
                target,
                allow_protected=True,
            )

            if snapshot.existed:
                if not snapshot.content_file:
                    raise DurableTransactionError(
                        "Missing snapshot content reference: "
                        f"{snapshot.relative_path}"
                    )
                content_path = self.files_root / snapshot.content_file
                if not content_path.is_file():
                    raise DurableTransactionError(
                        "Snapshot content is missing: "
                        f"{snapshot.relative_path}"
                    )
                content = content_path.read_bytes()
                if _sha256_bytes(content) != snapshot.sha256:
                    raise DurableTransactionError(
                        "Snapshot hash verification failed: "
                        f"{snapshot.relative_path}"
                    )
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
                restored[snapshot.relative_path] = "restored"
            else:
                if target.exists():
                    if not target.is_file():
                        raise DurableTransactionError(
                            "Rollback refused to delete a directory: "
                            f"{snapshot.relative_path}"
                        )
                    target.unlink()
                    restored[snapshot.relative_path] = "removed_created_file"
                else:
                    restored[snapshot.relative_path] = "already_absent"

        self._rolled_back = True
        self._active = False
        return restored

    def verify_snapshot_state(self) -> dict[str, bool]:
        results: dict[str, bool] = {}
        for snapshot in self._snapshots():
            target = self.workspace / snapshot.relative_path
            if not snapshot.existed:
                results[snapshot.relative_path] = not target.exists()
                continue
            if not target.is_file() or not snapshot.content_file:
                results[snapshot.relative_path] = False
                continue
            content_path = self.files_root / snapshot.content_file
            if not content_path.is_file():
                results[snapshot.relative_path] = False
                continue
            content = target.read_bytes()
            results[snapshot.relative_path] = (
                _sha256_bytes(content) == snapshot.sha256
                and content == content_path.read_bytes()
            )
        return results

    @classmethod
    def recover(
        cls,
        workspace: str | Path,
        transaction_id: str,
    ) -> "DurableCodingTransaction":
        transaction = cls(workspace, transaction_id=transaction_id)
        transaction._load_manifest()
        transaction._active = True
        transaction._rolled_back = False
        return transaction
