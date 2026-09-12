"""Best-effort silent updater for the packaged Windows desktop app."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import httpx

_REPO = "dragonballls/Friday"
_RELEASE_TAG = "desktop-latest"
_API = f"https://api.github.com/repos/{_REPO}"


def _build_sha() -> str:
    try:
        from build_info import BUILD_SHA
        return str(BUILD_SHA).strip()
    except Exception:
        return "dev"


def _state_path() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "Friday"
    root.mkdir(parents=True, exist_ok=True)
    return root / "update-state.json"


def _write_state(data: dict) -> None:
    path = _state_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def _get_json(url: str) -> dict:
    with httpx.Client(
        timeout=30.0,
        follow_redirects=True,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "Friday-Updater/1.0"},
    ) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.json()


def _latest_release() -> tuple[str, str] | None:
    release = _get_json(f"{_API}/releases/tags/{_RELEASE_TAG}")
    target_sha = str(release.get("target_commitish", "")).strip()
    for asset in release.get("assets", []):
        name = str(asset.get("name", ""))
        if name.lower().endswith("-setup.exe") and asset.get("browser_download_url"):
            return target_sha, str(asset["browser_download_url"])
    return None


def _download_installer(url: str, target_sha: str) -> Path:
    update_dir = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "Friday" / "updates" / target_sha
    update_dir.mkdir(parents=True, exist_ok=True)
    installer = update_dir / "Friday-latest-setup.exe"
    with httpx.Client(timeout=None, follow_redirects=True, headers={"User-Agent": "Friday-Updater/1.0"}) as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            with installer.open("wb") as handle:
                for chunk in response.iter_bytes(1024 * 1024):
                    handle.write(chunk)
    if not installer.exists() or installer.stat().st_size < 10_000_000:
        raise RuntimeError("Downloaded Friday installer failed validation")
    return installer


def _schedule_install(installer: Path) -> None:
    install_dir = Path(sys.executable).resolve().parents[1]
    app_exe = install_dir / "Friday.exe"
    script = installer.parent / "apply-update.cmd"
    script.write_text(
        "@echo off\r\n"
        ":wait\r\n"
        "tasklist /FI \"IMAGENAME eq Friday.exe\" | find /I \"Friday.exe\" >nul\r\n"
        "if not errorlevel 1 (timeout /t 2 /nobreak >nul & goto wait)\r\n"
        f'\"{installer}\" /S\r\n'
        f'if exist \"{app_exe}\" start \"\" \"{app_exe}\"\r\n'
        "del \"%~f0\"\r\n",
        encoding="utf-8",
    )
    subprocess.Popen(
        ["cmd.exe", "/c", str(script)],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        close_fds=True,
    )


def check_for_update() -> None:
    current = _build_sha()
    if not current or current == "dev":
        return
    try:
        latest = _latest_release()
        if latest is None:
            return
        target_sha, download_url = latest
        if not target_sha or target_sha == current:
            return
        state = {}
        try:
            state = json.loads(_state_path().read_text(encoding="utf-8"))
        except Exception:
            pass
        installer_path = Path(state.get("installer", ""))
        if state.get("target_sha") == target_sha and installer_path.exists():
            return
        installer = _download_installer(download_url, target_sha)
        _write_state({"target_sha": target_sha, "installer": str(installer)})
        _schedule_install(installer)
    except Exception:
        return


def start_background_check(delay_seconds: float = 8.0) -> None:
    def worker() -> None:
        time.sleep(delay_seconds)
        check_for_update()

    threading.Thread(target=worker, name="FridayUpdater", daemon=True).start()
