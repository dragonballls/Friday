"""Best-effort silent updater for the packaged Windows desktop app.

The updater follows the latest successful Build Friday Desktop artifact on main.
It only acts when the running sidecar was built from a different commit. The
installer is downloaded over HTTPS from GitHub Actions and scheduled to run
silently after the current Friday process exits.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from pathlib import Path

import httpx

_REPO = "dragonballls/Friday"
_WORKFLOW = "build-desktop.yml"
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
    with httpx.Client(timeout=30.0, follow_redirects=True, headers={"Accept": "application/vnd.github+json", "User-Agent": "Friday-Updater/1.0"}) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.json()


def _latest_build() -> tuple[str, str] | None:
    runs = _get_json(f"{_API}/actions/workflows/{_WORKFLOW}/runs?branch=main&status=success&per_page=10")
    for run in runs.get("workflow_runs", []):
        if run.get("head_sha"):
            artifacts = _get_json(f"{_API}/actions/runs/{run['id']}/artifacts?per_page=20")
            for artifact in artifacts.get("artifacts", []):
                if str(artifact.get("name", "")).startswith("Friday-Windows-x64-") and not artifact.get("expired", False):
                    return str(run["head_sha"]), str(artifact["archive_download_url"])
    return None


def _download_installer(artifact_url: str, target_sha: str) -> Path:
    update_dir = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "Friday" / "updates" / target_sha
    update_dir.mkdir(parents=True, exist_ok=True)
    zip_path = update_dir / "Friday-Windows-x64.zip"
    with httpx.Client(timeout=None, follow_redirects=True, headers={"Accept": "application/octet-stream", "User-Agent": "Friday-Updater/1.0"}) as client:
        with client.stream("GET", artifact_url) as response:
            response.raise_for_status()
            with zip_path.open("wb") as handle:
                for chunk in response.iter_bytes(1024 * 1024):
                    handle.write(chunk)

    with zipfile.ZipFile(zip_path) as archive:
        installer_names = [name for name in archive.namelist() if name.lower().endswith("-setup.exe")]
        if not installer_names:
            raise RuntimeError("Desktop update artifact did not contain a setup executable")
        archive.extract(installer_names[0], update_dir)
        installer = update_dir / installer_names[0]

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
    subprocess.Popen(["cmd.exe", "/c", str(script)], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), close_fds=True)


def check_for_update() -> None:
    current = _build_sha()
    if not current or current == "dev":
        return
    try:
        latest = _latest_build()
        if latest is None:
            return
        target_sha, artifact_url = latest
        if target_sha == current:
            return
        state = {}
        try:
            state = json.loads(_state_path().read_text(encoding="utf-8"))
        except Exception:
            pass
        if state.get("target_sha") == target_sha and Path(state.get("installer", "")).exists():
            return
        installer = _download_installer(artifact_url, target_sha)
        _write_state({"target_sha": target_sha, "installer": str(installer)})
        _schedule_install(installer)
    except Exception:
        return


def start_background_check(delay_seconds: float = 8.0) -> None:
    def worker() -> None:
        time.sleep(delay_seconds)
        check_for_update()

    threading.Thread(target=worker, name="FridayUpdater", daemon=True).start()
