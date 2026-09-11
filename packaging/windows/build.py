from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build" / "windows"
DIST = ROOT / "desktop" / "dist"
ENTRY = ROOT / "packaging" / "windows" / "app.py"
UPDATER_ENTRY = ROOT / "packaging" / "windows" / "updater.py"


def run(*args: str, workpath: Path | None = None) -> None:
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


def main() -> None:
    if not DIST.joinpath("index.html").is_file():
        raise SystemExit("desktop/dist/index.html is missing; run npm run build first")
    if not UPDATER_ENTRY.is_file():
        raise SystemExit(f"Windows updater entrypoint is missing: {UPDATER_ENTRY}")

    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True, exist_ok=True)

    separator = ";"
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        "Friday",
        "--onedir",
        "--distpath",
        str(BUILD),
        "--workpath",
        str(ROOT / "build" / "pyinstaller-work"),
        "--add-data",
        f"{DIST}{separator}desktop/dist",
        "--collect-all",
        "webview",
        "--collect-submodules",
        "core",
        "--collect-submodules",
        "agent",
        "--collect-submodules",
        "integrations",
        "--collect-submodules",
        "plugins",
        "--collect-submodules",
        "providers",
        str(ENTRY),
    ]

    prompts = ROOT / "prompts"
    if prompts.exists():
        cmd[cmd.index(str(ENTRY)):cmd.index(str(ENTRY))] = ["--add-data", f"{prompts}{separator}prompts"]

    run(*cmd)

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
