"""Cross-process guard preventing live source updates during active coding."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / ".jarvis_coding.lock"


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


def coding_update_locked() -> bool:
    if not LOCK_PATH.is_file():
        return False
    try:
        pid = int(LOCK_PATH.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return True
    if _pid_is_alive(pid):
        return True
    try:
        LOCK_PATH.unlink()
    except OSError:
        pass
    return False


def acquire_coding_lock() -> None:
    LOCK_PATH.write_text(str(os.getpid()), encoding="utf-8")


def release_coding_lock() -> None:
    try:
        LOCK_PATH.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass
