from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build" / "windows"
DIST = ROOT / "desktop" / "dist"
ENTRY = ROOT / "packaging" / "windows" / "app.py"


def run(*args: str) -> None:
    print("+", " ".join(args))
    subprocess.run(args, cwd=ROOT, check=True)


def main() -> None:
    if not DIST.joinpath("index.html").is_file():
        raise SystemExit("desktop/dist/index.html is missing; run npm run build first")

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

    exe = BUILD / "Friday" / "Friday.exe"
    if not exe.is_file():
        raise SystemExit(f"PyInstaller did not create {exe}")
    print(f"Windows bundle ready: {exe}")


if __name__ == "__main__":
    main()
