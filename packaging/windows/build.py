from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build" / "windows"
DIST = ROOT / "desktop" / "dist"
ENTRY = ROOT / "packaging" / "windows" / "app.py"
PROJECT_PACKAGES = ("desktop", "core", "agent", "integrations", "plugins", "providers", "browser", "config", "tools")
HIDDEN_IMPORTS = (
    "desktop.api_server",
    "quart",
    "quart_cors",
    "hypercorn",
    "hypercorn.asyncio",
    "google.auth",
    "google.auth.transport.requests",
    "google.oauth2.credentials",
    "google_auth_oauthlib.flow",
    "googleapiclient.discovery",
)

APP_FOLDER = "Friday-Barebones"
APP_NAME = "Friday-Barebones"


def run(*args: str) -> None:
    print("+", " ".join(args))
    subprocess.run(args, cwd=ROOT, check=True)


def current_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else "dev"


def app_pyinstaller_cmd() -> list[str]:
    separator = ";" if sys.platform == "win32" else sys.pathsep
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        APP_NAME,
        "--onedir",
        "--paths",
        str(ROOT),
        "--distpath",
        str(BUILD),
        "--workpath",
        str(ROOT / "build" / "pyinstaller-work"),
        "--add-data",
        f"{DIST}{separator}desktop/dist",
        "--collect-all",
        "webview",
        "--collect-all",
        "quart",
        "--collect-all",
        "hypercorn",
    ]
    for package in PROJECT_PACKAGES:
        cmd.extend(["--collect-submodules", package])
    for hidden in HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", hidden])

    prompts = ROOT / "prompts"
    if prompts.exists():
        cmd.extend(["--add-data", f"{prompts}{separator}prompts"])
    cmd.append(str(ENTRY))
    return cmd


def main() -> None:
    if not DIST.joinpath("index.html").is_file():
        raise SystemExit("desktop/dist/index.html is missing; run npm run build first")

    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True, exist_ok=True)

    run(*app_pyinstaller_cmd())

    exe = BUILD / APP_FOLDER / f"{APP_NAME}.exe"
    if not exe.is_file():
        raise SystemExit(f"PyInstaller did not create {exe}")

    (BUILD / APP_FOLDER / "VERSION").write_text(current_commit() + "\n", encoding="utf-8")
    print(f"Windows barebones bundle ready: {exe}")


if __name__ == "__main__":
    main()
