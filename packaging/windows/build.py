from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build" / "windows"
DIST = ROOT / "desktop" / "dist"
ENTRY = ROOT / "packaging" / "windows" / "app.py"
UPDATER_ENTRY = ROOT / "packaging" / "windows" / "updater.py"
PROJECT_PACKAGES = ("desktop", "core", "agent", "integrations", "plugins", "providers", "browser", "config", "tools")
HIDDEN_IMPORTS = (
    "desktop.api_server",
    "quart",
    "quart_cors",
    "hypercorn",
    "hypercorn.asyncio",
)


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


def console_requested() -> bool:
    return os.environ.get("FRIDAY_WINDOWS_CONSOLE", "").strip().lower() in {"1", "true", "yes"}


def app_pyinstaller_cmd(*, console: bool | None = None) -> list[str]:
    if console is None:
        console = console_requested()
    separator = ";" if os.name == "nt" else os.pathsep
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--clean",
        "--console" if console else "--windowed",
        "--name",
        "Friday",
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
    if not UPDATER_ENTRY.is_file():
        raise SystemExit(f"Windows updater entrypoint is missing: {UPDATER_ENTRY}")

    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True, exist_ok=True)

    run(*app_pyinstaller_cmd())

    updater_cmd = [
        "pyinstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        "FridayUpdater",
        "--onefile",
        "--distpath",
        str(BUILD / "Friday"),
        "--workpath",
        str(ROOT / "build" / "pyinstaller-work-updater"),
        str(UPDATER_ENTRY),
    ]
    run(*updater_cmd)

    exe = BUILD / "Friday" / "Friday.exe"
    updater = BUILD / "Friday" / "FridayUpdater.exe"
    if not exe.is_file():
        raise SystemExit(f"PyInstaller did not create {exe}")
    if not updater.is_file():
        raise SystemExit(f"PyInstaller did not create {updater}")

    (BUILD / "Friday" / "VERSION").write_text(current_commit() + "\n", encoding="utf-8")
    print(f"Windows bundle ready: {exe}")
    print(f"Windows updater ready: {updater}")


if __name__ == "__main__":
    main()
