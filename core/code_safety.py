"""Safety helpers for autonomous code changes."""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path


PROTECTED_PATH_PARTS = (
    ".env",
    "providers.toml",
    "Start-Friday.ps1",
    "core/security.py",
    "desktop/api_server.py",
)


def is_protected_path(path: str) -> bool:
    normalized = os.path.abspath(path).replace("\\", "/").lower()
    return any(
        normalized.endswith(part.lower()) or f"/{part.lower()}" in normalized
        for part in PROTECTED_PATH_PARTS
    )


def backup_file(path: str, backup_root: str | None = None) -> str | None:
    """Create a timestamped backup before replacing an existing file."""
    source = Path(path)
    if not source.is_file():
        return None

    root = Path(backup_root or source.parent / ".friday" / "backups")
    root.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(str(source).encode("utf-8")).hexdigest()[:10]
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    destination = root / f"{source.name}.{stamp}-{digest}.bak"
    shutil.copy2(source, destination)
    return str(destination)


def atomic_write(path: str, content: str) -> dict:
    """Back up and atomically replace a text file."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    backup = backup_file(str(destination))
    fd, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=str(destination.parent),
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
    return {"success": True, "backup": backup, "path": str(destination)}
