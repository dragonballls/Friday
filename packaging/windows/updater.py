from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path


def process_is_alive(pid: int) -> bool:
    result = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}"],
        capture_output=True,
        text=True,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return str(pid) in result.stdout


def wait_for_process_exit(pid: int, timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not process_is_alive(pid):
            return True
        time.sleep(0.5)
    return False


def find_bundle_root(extracted: Path) -> Path:
    direct = extracted / "Friday.exe"
    if direct.is_file():
        return extracted
    matches = list(extracted.rglob("Friday.exe"))
    if len(matches) != 1:
        raise RuntimeError("Downloaded Friday artifact did not contain exactly one Friday.exe")
    return matches[0].parent


def remove_tree(path: Path) -> None:
    if not path.exists():
        return
    shutil.rmtree(path, ignore_errors=False)


def replace_bundle(target: Path, extracted_bundle: Path, backup: Path) -> None:
    if target.exists():
        target.rename(backup)
    try:
        shutil.copytree(extracted_bundle, target)
    except Exception:
        if target.exists():
            remove_tree(target)
        if backup.exists():
            backup.rename(target)
        raise


def relaunch(exe: Path) -> subprocess.Popen:
    return subprocess.Popen(
        [str(exe), "--startup"],
        cwd=exe.parent,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Replace a running Friday Windows bundle safely")
    parser.add_argument("--pid", required=True, type=int)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--exe", required=True, type=Path)
    args = parser.parse_args()

    archive = args.archive.resolve()
    target = args.target.resolve()
    exe = args.exe.resolve()
    if not archive.is_file() or not target.is_dir():
        return 2

    work = Path(tempfile.mkdtemp(prefix="friday-updater-"))
    backup = target.with_name(f"{target.name}.backup")
    extracted = work / "extracted"
    try:
        if not wait_for_process_exit(args.pid):
            return 3
        if backup.exists():
            remove_tree(backup)
        extracted.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as bundle:
            bad = [name for name in bundle.namelist() if Path(name).is_absolute() or ".." in Path(name).parts]
            if bad:
                return 4
            bundle.extractall(extracted)
        downloaded_bundle = find_bundle_root(extracted)
        new_exe = downloaded_bundle / "Friday.exe"
        if not new_exe.is_file():
            return 5

        replace_bundle(target, downloaded_bundle, backup)
        new_target_exe = target / "Friday.exe"
        child = relaunch(new_target_exe)
        time.sleep(5)
        if child.poll() is not None:
            if target.exists():
                remove_tree(target)
            if backup.exists():
                backup.rename(target)
            relaunch(target / "Friday.exe")
            return 6

        if backup.exists():
            remove_tree(backup)
        return 0
    except (OSError, RuntimeError, zipfile.BadZipFile, ValueError):
        try:
            if target.exists() and backup.exists():
                remove_tree(target)
                backup.rename(target)
        except OSError:
            pass
        return 7
    finally:
        try:
            archive.unlink(missing_ok=True)
        except OSError:
            pass
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
